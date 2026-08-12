## Q1 - Celery task silently fails on retry

The bug is that `self.retry()` is called from inside a broad `except Exception` block without handling the terminal retry failure. Once `max_retries=3` is exhausted, the task must fail and the exception must propagate so that Celery and Sentry can record the failure.

I would explicitly re-raise the exception when the retry limit has been reached:

```python
@shared_task(bind=True, max_retries=3)
def process_video(self, video_id):
    try:
        video = PostVideo.objects.get(id=video_id)
        run_ffmpeg(video.file_path)

        video.status = 'done'
        video.save()

    except PostVideo.DoesNotExist:
        return

    except Exception as exc:
        if self.request.retries >= self.max_retries:
            logger.exception(
                "Video processing failed permanently",
                extra={"video_id": video_id},
            )
            raise

        raise self.retry(exc=exc, countdown=30)
```

This allows transient failures to retry while ensuring the final failure is not silently treated as a successful task. In production, I would also prefer catching only exceptions that are known to be transient rather than retrying every `Exception`.




## Q2 - Race condition in reward approval

The race condition is caused by the check-then-act sequence. Two concurrent requests can both read the reward while its status is still `claimed`, pass the status check, and both initiate a Paystack transfer before either request saves `approved`.

The minimal fix is to lock the reward row inside an atomic transaction:

```python
from django.db import transaction

@transaction.atomic
def approve_reward(request, reward_id):
    reward = Reward.objects.select_for_update().get(pk=reward_id)

    if reward.status != 'claimed':
        return Response({'error': 'Not claimable'}, status=400)

    result = PaystackService.initiate_transfer(
        amount=reward.amount,
        recipient=reward.paystack_recipient_code,
    )

    reward.status = 'approved'
    reward.transfer_code = result['transfer_code']
    reward.save()

    return Response({'detail': 'Approved'})
```

`select_for_update()` locks the reward row until the transaction completes, so concurrent requests cannot both pass the `claimed` check.

For a production payment system, I would additionally use an idempotency mechanism for the external transfer, since a successful Paystack transfer followed by a database failure could otherwise still result in a duplicate transfer on retry.



## Q3 - Migration will fail on a live table

Adding a non-nullable `unique=True` field directly to a table with 500,000 existing rows is unsafe. Existing rows have no value for `content_hash`, and assigning the same default value to all rows would violate the unique constraint. Depending on the database, the DDL can also require a long-running table lock.

I would use a multi-step migration:

1. Add `content_hash` as nullable and without the unique constraint.
2. Backfill hashes for existing rows in batches, without holding one large transaction.
3. Verify that all existing values are populated and unique.
4. Add the unique constraint/index safely. On PostgreSQL, I would consider creating the unique index concurrently to minimize locking.
5. Once the data is populated and the constraint is enforced, make the field non-nullable if required.

The key is to separate the schema change, data backfill, and constraint enforcement rather than adding a required unique column to 500,000 existing rows in a single migration.



## Q4 - Celery task design

I would keep notification delivery asynchronous and separate the fan-out from the API request that publishes the post.

A naive implementation that loops through all 50,000 followers in one Celery task creates a long-running task. If one notification fails, retrying could resend all previous notifications. It can also monopolize a worker and put unnecessary pressure on the database and push-notification provider.

I would fetch only the required follower/device IDs using `values_list()` and process them in batches, for example 500–1,000 recipients per Celery task:

```text
Post published
      ↓
Fan-out Celery task
      ↓
Fetch follower IDs in batches
      ↓
Batch notification tasks
      ↓
Push notification provider
```

Each batch is independently retryable, so a failure only affects that batch rather than the entire 50,000-recipient operation. I would also control worker concurrency/rate limits to avoid overwhelming the push provider.

Because Celery tasks can be retried, notification delivery should be idempotent where possible. I would use a unique `(post_id, follower_id)` delivery record or a provider-supported idempotency key to prevent duplicate notifications.

The publish endpoint itself should only enqueue the fan-out task and return without waiting for notification delivery.



## Q5 - Database index decision

I would add a composite index covering both filter columns and the ordering column:

```python
class Meta:
    indexes = [
        models.Index(
            fields=['assigned_operator', 'status', '-created_at'],
            name='ticket_operator_status_created_idx',
        ),
    ]
```

The query filters on `assigned_operator` and `status`, then orders by `created_at DESC`. A single composite index matches this access pattern and allows the database to find the relevant rows in the required order, making the `LIMIT 20` efficient.

Without the index, the planner may use a sequential scan followed by a sort:

```text
Seq Scan on support_ticket
  Filter: (status = 'open' AND assigned_operator_id = ...)
Sort
  Sort Key: created_at DESC
Limit 20
```

After the index, I would expect an index scan using the composite index, with no separate sort:

```text
Index Scan using ticket_operator_status_created_idx
  Index Cond: (assigned_operator_id = ... AND status = 'open')
Limit 20
```

The exact plan depends on the database statistics and data distribution, so I would verify it with `EXPLAIN (ANALYZE, BUFFERS)` before and after adding the index.



## Q6 - Debugging a production spike

My first three checks would be:

1. **Celery logs around 4am:** Identify which tasks were running immediately before the worker received SIGKILL. I would look for long-running tasks, repeated retries, unusually large workloads, or tasks continuously spawning additional work.

2. **CloudWatch CPU timeline:** Correlate the timing of the CPU increase with the Celery workload. I would check whether CPU increased suddenly or gradually and whether it dropped after the worker was killed. This helps establish whether the worker workload is actually responsible.

3. **The code for the suspected task:** Once I identify the likely workload, I would inspect it for CPU-intensive operations, inefficient ORM/query processing, large Python loops, accidental infinite/recursive work, excessive concurrency, or retry/fan-out behavior.

`SIGKILL` means the worker was externally terminated; it is not a normal Python exception. I would investigate resource exhaustion, including possible OOM conditions, but I would not conclude that memory exhaustion was the cause without supporting evidence because the available CloudWatch data only includes CPU.

The goal is to correlate the CPU spike with a specific Celery workload before making a code or infrastructure change.


## Q7 - Security review

There are several security issues:

### 1. Account enumeration

Returning `404 No account found` reveals whether an email address is registered.

**Risk:** Attackers can enumerate valid accounts.

**Fix:** Always return the same generic response, for example:

```json
{"detail": "If the account exists, a reset email has been sent."}
```

### 2. Weak reset token

`random.randint(1000, 9999)` provides only 10,000 possible values and `random` is not suitable for security-sensitive tokens.

**Risk:** The token can be brute-forced.

**Fix:** Generate a cryptographically secure token using `secrets` or Django's password-reset token mechanism.

```python
import secrets

token = secrets.token_urlsafe(32)
```

### 3. Token stored in plaintext

The reset token is stored directly on the user record.

**Risk:** A database compromise could expose active reset credentials.

**Fix:** Prefer Django's built-in password-reset mechanism or store a hash of a securely generated token.

### 4. No token expiration or one-time use

There is no expiration or invalidation shown.

**Risk:** A stolen token could remain usable indefinitely.

**Fix:** Store an expiration timestamp and invalidate the token after successful use or when a new reset is requested.

### 5. No rate limiting

The endpoint is unauthenticated and can queue reset emails repeatedly.

**Risk:** Brute-force attempts, email flooding, and abuse of the email service.

**Fix:** Apply rate limiting/throttling based on IP and account/email, while still returning a generic response.

`AllowAny` itself is not a vulnerability here because users must be able to initiate a password reset without being authenticated.



## Q8 - Django Management Command

### Explaination for answer in ```rewards/management/commands/audit_stale_rewards.py```

The command uses a read-only queryset for the default dry-run mode. No update occurs unless `--fix` is explicitly provided.

The stale condition is:

```python
status="claimed",
claimed_at__lt=timezone.now() - timedelta(days=7)
```

The summary is calculated by the database using `Count()` grouped by `reward_type`.

When `--fix` is provided, rewards are processed in batches to avoid loading the entire result set into memory, and `bulk_update()` reduces the number of database writes. Each expired reward ID is logged at INFO level as required.

All timestamps use Django's timezone-aware `timezone.now()`.


