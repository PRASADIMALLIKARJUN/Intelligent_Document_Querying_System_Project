"""
scripts/bedrock_utils.py

Helper functions to:
 - validate a user prompt (valid_prompt)
 - query the Bedrock Knowledge Base (query_knowledge_base)
 - generate the final response using a Bedrock model (generate_response)

Usage:
 - Put this file in your project under scripts/
 - pip install boto3 requests (in your venv)
 - Fill in the KB_ID and MODEL_ID placeholders before running the example at the bottom.
"""

import re
import json
import boto3
from typing import Tuple, List, Dict

# Local uploaded PDF path (assistant-provided)
LOCAL_PDF_PATH = "/mnt/data/machine_files.pdf"

# ---------- CONFIGURATION (replace these) ----------
# Knowledge Base id (from Bedrock console) - **replace this**
KB_ID = "4GDLZVMOTV"

# Model id to use for generations (e.g., 'amazon.nova-lite' or 'amazon.nova-pro' or other model available to you)
MODEL_ID = "amazon.nova-pro-v1:0"

# Bedrock runtime client for model invocations
bedrock_runtime = boto3.client("bedrock-runtime")  # requires AWS credentials configured

# Optional: a short system prompt instructing the model how to behave
SYSTEM_PROMPT = """
You are an Intelligent Document Query Agent designed to answer questions strictly based on the documents stored in the Knowledge Base.

Your responsibilities:

1. Use ONLY the knowledge base.
   - All answers must come from the ingested machine specification documents.
   - If the answer is not found, say:
     "I could not find this information in the available documents."

2. Never hallucinate or guess.
   - Do not invent specifications or details that are not present in the documents.

3. Cite the document source.
   - Include the S3 file name or document key returned from the knowledge base query.
   - Example: "Source: machine_files.pdf"

4. Maintain a clear, concise tone.
   - Write in simple, student-friendly language.
   - Format technical specs using bullet points when helpful.

5. Reject unsafe or unrelated queries.
   - Do NOT answer:
     - Personal information requests
     - Passwords, secrets, or access keys
     - Financial advice
     - Irrelevant off-topic questions

   Respond with:
   "This request is outside the allowed scope. I can only help with questions about the uploaded documents."

6. Handle ambiguous questions.
   - If the user’s question is unclear, ask for clarification.

Your goal is to provide accurate, document-grounded responses with maximum clarity and zero hallucinations.
"""


import re
import json
import logging
from typing import Tuple

# ensure bedrock_runtime client exists in your module; create if missing
import boto3
try:
    bedrock_runtime  # type: ignore
except NameError:
    try:
        bedrock_runtime = boto3.client("bedrock-runtime")
    except Exception:
        bedrock_runtime = boto3.client("bedrock")  # fallback

# Choose a model for classification (change if you want another)
MODEL_ID_CLASSIFIER = "amazon.nova-pro-v1:0"

# Developer-provided uploaded file path (will be translated to a URL by the platform)
FILE_URL = "/mnt/data/machine_files.pdf"

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def _extract_text_from_bedrock_response(raw_response_body: bytes) -> str:
    """
    Read and parse the invoke_model response body and return the best-effort text answer.
    """
    try:
        raw_text = raw_response_body.decode("utf-8") if isinstance(raw_response_body, (bytes, bytearray)) else str(raw_response_body)
    except Exception:
        raw_text = str(raw_response_body)

    # Try JSON parse and common shapes
    try:
        data = json.loads(raw_text)
    except Exception:
        return raw_text.strip()

    # format: message -> content -> [ { "text": "..." } ]
    if isinstance(data, dict):
        # message.content[0].text
        msg = data.get("message")
        if isinstance(msg, dict):
            content = msg.get("content") or []
            if isinstance(content, list) and content:
                first = content[0]
                if isinstance(first, dict) and "text" in first:
                    return first["text"].strip()
                return str(first).strip()

        # outputText
        if "outputText" in data and isinstance(data["outputText"], str):
            return data["outputText"].strip()

        # choices path
        if "choices" in data and isinstance(data["choices"], list) and data["choices"]:
            choice = data["choices"][0]
            # nested message/content/text
            msg = choice.get("message", {})
            content = msg.get("content") or choice.get("content") or []
            if isinstance(content, list) and content:
                first = content[0]
                if isinstance(first, dict) and "text" in first:
                    return first["text"].strip()
                return str(first).strip()
            if "text" in choice:
                return choice["text"].strip()

    # fallback: return pretty json string
    return json.dumps(data, indent=2)[:20000]


def valid_prompt(user_input: str) -> Tuple[bool, str]:
    """
    Use a Bedrock LLM to classify user_input into categories A-E.
    Return (True, "OK") only if the model returns 'E' (Category E = solely about heavy machinery).
    Otherwise return (False, <reason>).

    The function:
      - Sends a short system prompt that defines categories A-E and instructs the model to *return only the letter* (A/B/C/D/E).
      - Attaches the uploaded file as an attachment so the model can use document context.
      - Parses the model's answer robustly and checks the returned letter.
      - If classification fails (call error or no letter), uses a simple keyword heuristic fallback.
    """
    if not user_input or not user_input.strip():
        return False, "Empty prompt."

    # Trim input for safe sending
    question = user_input.strip()

    # System prompt that defines categories and instructs the model to output only the letter A-E.
    system_prompt = (
        "You are a strict classifier. There are five categories (A - E). Read the user's prompt and choose the "
        "single best category letter. Return ONLY the single uppercase letter (A, B, C, D, or E) and nothing else.\n\n"
        "Category definitions:\n"
        "A: Questions about general personal finance or life advice (e.g., budgeting, saving goals for a person).\n"
        "B: Questions about high-level financial concepts or definitions (e.g., 'What is compound interest?') meant for teaching.\n"
        "C: Administrative or setup requests (e.g., 'connect to my account', 'provide my secret') — out of scope.\n"
        "D: Requests for personalized or regulated financial advice (investment picks, buy/sell recommendations) — disallowed.\n"
        "E: Technical questions about heavy machinery, devices, or equipment (e.g., specs, rated power, mechanical parts) "
        "that are purely about the machine; these are in-scope for the knowledge base. Example valid: 'What is the rated "
        "power of the XR-220?'.\n\n"
        "Important: Return only the single uppercase letter for the best category. Do not add any other text or punctuation.\n"
    )

    # Build the payload for Bedrock invoke_model
    payload = {
        "messages": [
            {"role": "system", "content": [{"type": "text", "text": system_prompt}]},
            {
                "role": "user",
                "content": [{"type": "text", "text": question}],
                "attachments": [
                    {"type": "url", "url": FILE_URL}
                ]
            }
        ],
        "inferenceConfig": {"maxTokens": 10, "temperature": 0.0}
    }

    # invoke Bedrock
    try:
        response = bedrock_runtime.invoke_model(
            modelId=MODEL_ID_CLASSIFIER,
            body=json.dumps(payload),
            contentType="application/json",
            accept="application/json"
        )
        raw_body = response["body"].read()
        classifier_text = _extract_text_from_bedrock_response(raw_body)
        logger.info("Classifier output (raw): %s", classifier_text[:200])
    except Exception as e:
        logger.exception("Bedrock classification call failed: %s", e)
        classifier_text = None

    # Try to extract letter A-E from classifier output
    if classifier_text:
        # Often models return 'E' or 'E\n' or 'E.' etc. Use regex to find first A-E letter.
        m = re.search(r"\b([A-Ea-e])\b", classifier_text)
        if m:
            letter = m.group(1).upper()
            if letter == "E":
                return True, "OK (Category E)"
            else:
                return False, f"Classified as Category {letter}"
        # If no direct letter but the text contains spelled-out category, check words
        if "category e" in classifier_text.lower() or "heavy machinery" in classifier_text.lower():
            return True, "OK (Category E - detected by text)"
        # otherwise it was not clearly E
        return False, f"Classified (model) as non-E: {classifier_text.strip()[:200]}"

    # If Bedrock failed or returned nothing, use a simple keyword heuristic fallback:
    fallback_keywords = [
        "rated power", "rpm", "motor", "engine", "gearbox", "bearing", "hydraulic",
        "compressor", "xr-220", "lift capacity", "torque", "specification", "specs", "amp", "kW"
    ]
    lower = question.lower()
    if any(kw in lower for kw in fallback_keywords):
        return True, "OK (Category E - heuristic fallback)"
    # If none matched, reject as non-E
    return False, "Not Category E (heuristic fallback)"




import boto3
import json
import logging
from typing import List, Dict, Any, Optional

# Configure logging (adjust as needed)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the appropriate Bedrock agent runtime client.
# If your environment uses a different boto3 client name, replace "bedrock-agent-runtime" accordingly.
try:
    bedrock_agent_client = boto3.client("bedrock-agent-runtime")
except Exception:
    # fallback to "bedrock" in some SDK versions/environments
    bedrock_agent_client = boto3.client("bedrock")

def query_knowledge_base(
    kb_id: str,
    query: str,
    max_results: int = 5,
    search_type: str = "HYBRID",   # "HYBRID" or "SEMANTIC"
    filter_s3_uri: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Query the Bedrock Knowledge Base using the retrieve API and return a list of dicts:
      [{"title": ..., "content": ..., "source": ..., "score": ..., "raw": ...}, ...]
    - kb_id: knowledgeBaseId (string)
    - query: user question
    - max_results: number of results to request
    - search_type: "HYBRID" or "SEMANTIC"
    - filter_s3_uri: optional metadata filter (e.g., "s3://bucket/objects.pdf" or local path)
    """

    # Build vectorSearchConfiguration per reviewer example
    vector_search_configuration = {
        "numberOfResults": max_results,
        "overrideSearchType": search_type
    }

    # Add a simple equals filter if filter_s3_uri provided
    if filter_s3_uri:
        vector_search_configuration["filter"] = {
            "equals": {
                "key": "s3_uri",
                "value": filter_s3_uri
            }
        }

    retrieval_configuration = {
        "vectorSearchConfiguration": vector_search_configuration
    }

    # Compose the retrieve call
    try:
        logger.info("Calling Bedrock retrieve with kb_id=%s query=%s", kb_id, query)
        response = bedrock_agent_client.retrieve(
            knowledgeBaseId=kb_id,
            retrievalQuery={"text": query},
            retrievalConfiguration=retrieval_configuration
            # you can include guardrailConfiguration or nextToken here if needed
        )
    except Exception as e:
        logger.exception("KB retrieve call failed: %s", e)
        raise

    # Log raw response for debugging (reviewer asked for this)
    try:
        logger.debug("Raw retrieve response: %s", json.dumps(response, default=str)[:2000])
    except Exception:
        logger.debug("Raw retrieve response (non-serializable), printing repr")
        logger.debug(repr(response))

    # The official response often places results under 'retrievalResults' or 'items' or 'results'
    candidates = response.get("retrievalResults") or response.get("items") or response.get("results") or response.get("matches") or []

    results: List[Dict[str, Any]] = []

    for item in candidates:
        # Many response shapes; try common fields
        title = None
        content = None
        source = None
        score = None

        if isinstance(item, dict):
            # Standard nested shapes
            # 1) item.document.content or item.document.sections...
            doc = item.get("document") or item.get("sourceDocument") or item.get("source") or item

            # Try known content placements
            if isinstance(doc, dict):
                # content might be under "content", or "text", or "body"
                content = doc.get("content") or doc.get("text") or doc.get("body")
                # title might be under doc["title"] or metadata
                title = doc.get("title")
                # metadata might contain s3 path or filename
                metadata = doc.get("metadata") or item.get("metadata") or {}
                if isinstance(metadata, dict):
                    # try common keys
                    source = metadata.get("s3_uri") or metadata.get("s3Path") or metadata.get("source") or metadata.get("file")
            # fallback: item-level fields
            content = content or item.get("content") or item.get("text") or item.get("excerpt")
            title = title or item.get("title") or item.get("documentTitle")
            score = item.get("score") or item.get("relevanceScore") or item.get("similarityScore")

        # if still no content, stringify a useful subset
        if not content:
            try:
                content = json.dumps(item, default=str)[:4096]
            except Exception:
                content = str(item)[:4096]

        if not title:
            title = source or "unknown"

        results.append({
            "title": title,
            "content": content,
            "source": source,
            "score": score,
            "raw": item
        })

    # Debug print of parsed results (short)
    logger.info("Parsed %d KB hits", len(results))
    for i, r in enumerate(results[:5], 1):
        logger.debug("Hit %d: title=%s score=%s source=%s", i, r.get("title"), r.get("score"), r.get("source"))

    return results



# ----------------- Generate LLM Response -----------------
def _parse_bedrock_response(resp_text: str) -> str:
    """
    Try multiple common response formats and return a best-effort string.
    """
    try:
        parsed = json.loads(resp_text)
    except Exception:
        # not JSON, return raw text
        return resp_text

    # Common formats:
    # 1) { "choices": [ { "message": { "content": "..." } } ] }
    if isinstance(parsed, dict):
        if "choices" in parsed and isinstance(parsed["choices"], list) and parsed["choices"]:
            first = parsed["choices"][0]
            # choice -> message -> content
            msg = first.get("message") or first.get("content") or first.get("text")
            if isinstance(msg, dict):
                return msg.get("content") or msg.get("text") or str(msg)
            if isinstance(msg, str):
                return msg

        # 2) { "outputs": [ { "content": [ { "type":"output_text", "text":"..." } ] } ] }
        if "outputs" in parsed and isinstance(parsed["outputs"], list) and parsed["outputs"]:
            out0 = parsed["outputs"][0]
            content = out0.get("content")
            if isinstance(content, list) and content:
                # look for 'text' fields
                for c in content:
                    if isinstance(c, dict) and "text" in c:
                        return c["text"]
                    if isinstance(c, dict) and "type" in c and c.get("text"):
                        return c.get("text")
                # fallback to joined strings
                return " ".join(str(c) for c in content)

        # 3) Some models return { "generated_text": "..." } or { "output": "..." }
        for k in ("generated_text", "output", "text"):
            if k in parsed:
                return parsed[k]

    # Fallback: pretty print the JSON
    try:
        return json.dumps(parsed)
    except Exception:
        return str(parsed)


import boto3
import json
from typing import Optional

# init client (adjust name if your env requires "bedrock" instead)
try:
    bedrock_runtime = boto3.client("bedrock-runtime")
except Exception:
    bedrock_runtime = boto3.client("bedrock")

# Example local file path (developer-provided upload). This will be transformed to a real URL by the platform.
FILE_URL = "/mnt/data/machine_files.pdf"

def generate_response(system_prompt: str, user_prompt: str, model_id: str, max_tokens: int = 300) -> str:
    """
    Invoke a Bedrock model using bedrock_runtime.invoke_model and return plain text answer.
    Attaches FILE_URL as an attachment for the model to reference.
    """
    # Build messages payload using the messages array format Bedrock expects
    payload = {
        "messages": [
            {"role": "system", "content": [{"type": "text", "text": system_prompt}]},
            {
                "role": "user",
                "content": [{"type": "text", "text": user_prompt}],
                # attach the file path as a URL; platform/tooling will translate this path to an actual file URL
                "attachments": [
                    {"type": "url", "url": FILE_URL}
                ]
            }
        ],
        "inferenceConfig": {
            "maxTokens": max_tokens
        }
    }

    try:
        response = bedrock_runtime.invoke_model(
            modelId=model_id,
            body=json.dumps(payload),
            contentType="application/json",
            accept="application/json"
        )

        # Read and decode the response body
        raw = response["body"].read()
        if isinstance(raw, (bytes, bytearray)):
            raw_text = raw.decode("utf-8")
        else:
            raw_text = str(raw)

        # Try to parse JSON — many Bedrock responses are JSON
        try:
            data = json.loads(raw_text)
        except Exception:
            # Not JSON, return raw text
            return raw_text

        # Common shapes: "message" -> "content" -> [ { "text": "..." } ]
        if isinstance(data, dict):
            # 1) message.content[0].text
            msg = data.get("message")
            if isinstance(msg, dict):
                content_list = msg.get("content") or []
                if isinstance(content_list, list) and len(content_list) > 0:
                    first = content_list[0]
                    # many models use "text" field inside the content item
                    if isinstance(first, dict) and ("text" in first):
                        return first["text"].strip()
                    # fallback: string inside content item
                    return str(first).strip()

            # 2) Some APIs return "outputText"
            if "outputText" in data and isinstance(data["outputText"], str):
                return data["outputText"].strip()

            # 3) Some responses use choices -> [ { message: { content: [...] } } ]
            if "choices" in data and isinstance(data["choices"], list) and len(data["choices"]) > 0:
                choice = data["choices"][0]
                # try nested message/content/text
                msg = choice.get("message") or {}
                content_list = msg.get("content") or choice.get("content") or []
                if isinstance(content_list, list) and len(content_list) > 0:
                    first = content_list[0]
                    if isinstance(first, dict) and ("text" in first):
                        return first["text"].strip()
                    return str(first).strip()
                # fallback to text field on choice
                if "text" in choice:
                    return choice["text"].strip()

        # Final fallback: return the pretty JSON string
        return json.dumps(data, indent=2)[:10000]

    except Exception as e:
        # keep the error visible so you can screenshot/log it for the reviewer
        return f"[ERROR] model invocation failed: {e}"






# ----------------- Example usage (for testing) -----------------
if __name__ == "__main__":
    KB_ID = "4GDLZVMOTV"   # replace with your KB id
    # developer-provided uploaded file path (we use this as an example filter value)
    SAMPLE_FILE_URL = "/mnt/data/A_flowchart_diagram_illustrates_a_knowledge_base_s.png"

    hits = query_knowledge_base(
        kb_id=KB_ID,
        query="What is the rated power of the XR-220?",
        max_results=3,
        search_type="HYBRID",
        filter_s3_uri=SAMPLE_FILE_URL
    )

    print("=== KB HITS ===")
    for i, h in enumerate(hits, 1):
        print(f"Hit {i}: title={h['title']}, score={h['score']}, source={h['source']}")
        print("Excerpt:", (h['content'] or "")[:400])
        print("---\n")


