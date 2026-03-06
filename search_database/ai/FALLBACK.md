**The Solution: Hashing & Local Caching**
Instead of scraping the webpage and sending it straight to `langextract`, generate an MD5 hash of the URL or PDF file. Save the raw scraped text to a local `/tmp/` directory or a fast Redis cache under that hash.
If your pipeline breaks, your script checks the cache first. You save massive amounts of input tokens by never downloading or parsing the same HTML twice.

### 3. The Overprocedure: Handling Validation Failures

When `langextract` outputs data and Pydantic catches a `ValidationError`, you need a multi-stage fallback. Do not just drop the data, and do not run the entire heavy extraction again.

Here is the industry-standard fallback loop:

#### Stage 1: The Cheap "Self-Correction" Call (Max Retries: 1)

If Pydantic fails, do not send the whole webpage back to the LLM. That costs thousands of tokens. Instead, catch the specific error, and send a tiny, incredibly cheap prompt back to the LLM containing _only_ the broken JSON and the exact Pydantic error message.

```python
from pydantic import ValidationError

def correct_bad_extraction(bad_json_dict, error_message):
    """A tiny, cheap LLM call to fix formatting."""
    correction_prompt = f"""
    You are a JSON fixing assistant.
    The following JSON failed validation with this error: {error_message}

    Data: {bad_json_dict}

    Fix the data types and return the corrected JSON. Do not change the information.
    """
    # Send THIS to your LLM. It takes ~50 input tokens instead of 50,000.
    # Return the fixed dict.

```

#### Stage 2: The Dead Letter Queue (DLQ)

If the self-correction fails (or you hit your max retry limit of 1 to save money), you trigger the ultimate safety net: a Dead Letter Queue.

In data engineering, a DLQ is a specific database table where failed processes go to wait for human intervention, ensuring your main ingestion script doesn't crash.

**How to build it in Django:**
Create a simple model in your `search_database/models.py`:

```python
class FailedExtraction(models.Model):
    source_link = models.URLField()
    raw_ai_output = models.JSONField(help_text="The broken dictionary the LLM returned")
    error_message = models.TextField(help_text="The Pydantic validation error")
    created_at = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False)

```

**The Final Pipeline Logic:**

```python
for ext in result.extractions:
    raw_data = {"raw_text": ext.extraction_text, **ext.attributes}

    try:
        # 1. Try normal validation
        clean_citation = CitationSchema(**raw_data)
        # ... save to DB ...

    except ValidationError as e:
        # 2. Trigger Stage 1: Cheap Self-Correction
        try:
            fixed_data = correct_bad_extraction(raw_data, str(e))
            clean_citation = CitationSchema(**fixed_data)
            # ... save to DB ...

        except Exception as final_error:
            # 3. Trigger Stage 2: Dead Letter Queue
            print(f"Extraction fatally failed. Routing to DLQ.")
            FailedExtraction.objects.create(
                source_link=url,
                raw_ai_output=raw_data,
                error_message=str(final_error)
            )

```

---

# Adjusted Plan

1. First check the how the langextract retrived the information
2. Check if the pydantic correctly validates the information or are there any false positives
3. Check the integrations of these both works correctly or not
4. Apply the fallback loop and human in the loop strategy also use langgraph for strucutured information state management if required
5. Create script for storing the data into database using redis and celery
6. First figure out these then start thingking from here to froward
