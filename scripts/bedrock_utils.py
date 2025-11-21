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


def valid_prompt(user_input: str) -> Tuple[bool, str]:
    """
    Check prompt for disallowed requests (PII scraping, illegal or risky financial advice, etc.)
    Returns (is_valid, reason). If is_valid is False, reason explains why.
    """
    text = user_input.lower().strip()

    # Disallow requests for PII (phone numbers, addresses, SSNs, emails)
    phone_regex = r"(\+?\d{1,3}[\s-]?)?(\(?\d{3}\)?[\s-]?)?\d{3}[\s-]?\d{4}"
    email_regex = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
    ssn_regex = r"\b\d{3}-\d{2}-\d{4}\b"
    address_keywords = ["address", "home address", "phone number", "mobile number", "contact number"]

    if re.search(phone_regex, text) or re.search(email_regex, text) or re.search(ssn_regex, text):
        return False, "The request appears to ask for personal contact information; this is not allowed."

    if any(kw in text for kw in address_keywords):
        return False, "The request asks for personal contact or address details; I cannot provide that."

    # Disallow explicit investment/trading advice that is personalized
    if any(kw in text for kw in ["should i buy", "stock", "buy shares", "investment advice", "which stock"]):
        return False, "I cannot give personalized investment advice."

    # Disallow instructions for wrongdoing
    if any(kw in text for kw in ["how to hack", "how to steal", "illegal", "bomb", "explosive"]):
        return False, "I cannot assist with harmful or illegal activities."

    # Allow everything else
    return True, "OK"


import boto3
import json
from typing import List, Dict, Any, Optional

# Initialize once (top of file)
bedrock_client = boto3.client("bedrock")  # matches sample retrieve API

def query_knowledge_base(
    kb_id: str,
    query: str,
    max_results: int = 5,
    search_type: str = "HYBRID",   # or "SEMANTIC"
    filter_s3_uri: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Query the Bedrock Knowledge Base using the `retrieve` API and return a
    list of results with the shape:
      [{"title": ..., "content": ..., "source": ..., "score": ...}, ...]

    - kb_id: the knowledgeBaseId (string)
    - query: user question text
    - max_results: number of results to request
    - search_type: "HYBRID" or "SEMANTIC"
    - filter_s3_uri: optional value to restrict results by metadata key 's3_uri'
    """
    # Build vectorSearchConfiguration
    vector_search_cfg = {
        "numberOfResults": max_results,
        "overrideSearchType": search_type
    }

    # Optional simple equality filter on metadata (example: use the local path as URL)
    # value can be like "s3://your-bucket/documents/machine_files.pdf" or the local path
    if filter_s3_uri:
        vector_search_cfg["filter"] = {
            "equals": {
                "key": "s3_uri",
                "value": filter_s3_uri
            }
        }

    retrieval_configuration = {
        "vectorSearchConfiguration": vector_search_cfg
    }

    try:
        response = bedrock_client.retrieve(
            knowledgeBaseId=kb_id,
            retrievalQuery={"text": query},
            retrievalConfiguration={"vectorSearchConfiguration": vector_search_cfg}
            # If you have guardrails or nextToken to add, include them here
        )
    except Exception as e:
        # Keep failure visible to caller
        raise RuntimeError(f"KB retrieve failed: {e}")

    # Parse results robustly. The exact response shape can vary; handle common fields:
    results = []
    # Two common locations: response.get("items") or response.get("results")
    candidates = response.get("items") or response.get("results") or response.get("matches") or []
    for item in candidates:
        # Try several likely nested shapes to extract content/title/source/score
        title = None
        content = None
        source = None
        score = None

        # Example shape: item["document"]["content"] or item["content"]
        if isinstance(item, dict):
            # document block
            doc = item.get("document") or item.get("sourceDocument") or item
            # content text
            content = (
                doc.get("content") if isinstance(doc, dict) else None
            ) or item.get("content") or item.get("text") or None

            # title/file name
            title = (
                doc.get("title") if isinstance(doc, dict) else None
            ) or item.get("title") or (doc.get("s3Path") if isinstance(doc, dict) else None)

            # source metadata (s3 path or metadata field)
            metadata = (doc.get("metadata") if isinstance(doc, dict) else None) or item.get("metadata")
            if metadata:
                # try known metadata keys
                source = metadata.get("s3_uri") or metadata.get("source") or metadata.get("file") or None

            # score / relevance
            score = item.get("score") or item.get("relevanceScore") or None

        # Fallback: stringify the item
        if not content:
            content = json.dumps(item)[:4096]  # avoid massive blobs

        # Ensure a readable title/source
        if not title:
            title = source or "unknown"

        results.append({
            "title": title,
            "content": content,
            "source": source,
            "score": score,
            "raw": item  # keep raw piece for debugging if needed
        })

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


def generate_response(system_prompt: str, user_prompt: str, model_id: str = MODEL_ID) -> str:
    """
    Final attempt: build messages where messages[0].content is a JSON array of objects
    that ONLY contain 'text' keys. Include the local file path inside a text object.
    If that fails, fall back to a single-string messages payload.
    """
    # 1) Validate prompt
    ok, reason = valid_prompt(user_prompt)
    if not ok:
        return f"Request denied: {reason}"

    # 2) Get KB context
    kb_results = query_knowledge_base(KB_ID, user_prompt, max_results=3)
    context_parts = []
    for r in kb_results:
        content = r.get("content", "")
        title = r.get("title", "Source")
        context_parts.append(f"Source: {title}\n{content}")
    kb_context = "\n\n".join(context_parts) if context_parts else "No KB context found."

    # 3) Build content array with ONLY 'text' fields
    # Put system instructions and user question in the first text object,
    # KB context in the second, and local file path in the third (as text).
    local_file_path = "/mnt/data/machine_files.pdf"  # from conversation history

    first_text = {
        "text": (
            f"{system_prompt}\n\nUser question: {user_prompt}\n\n"
            "Answer ONLY from the knowledge base documents. Cite the document file name when possible."
        )
    }
    kb_text = {
        "text": f"Knowledge Base context:\n{kb_context}"
    }
    file_text = {
        "text": f"Local document path (for reference): {local_file_path}"
    }

    content_array = [first_text, kb_text, file_text]

    # Primary payload: messages with content as JSONArray of text objects
    payload_primary = {
        "messages": [
            {"role": "user", "content": content_array}
        ]
    }

    # Fallback payload: messages with single string content (some endpoints accept this)
    fallback_message = (
        f"{system_prompt}\n\nUser question: {user_prompt}\n\n"
        f"Knowledge Base context:\n{kb_context}\n\n"
        f"Local document path (for reference): {local_file_path}\n\n"
        "Answer ONLY from the knowledge base documents. Cite the document file name when possible."
    )
    payload_fallback = {
        "messages": [
            {"role": "user", "content": fallback_message}
        ]
    }

    # Try primary format first, then fallback
    try:
        response = bedrock_runtime.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(payload_primary)
        )
        raw = response["body"].read().decode("utf-8")
        return _parse_bedrock_response(raw)
    except Exception as e_primary:
        # If primary fails, try fallback once and return more informative message if both fail
        try:
            response = bedrock_runtime.invoke_model(
                modelId=model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(payload_fallback)
            )
            raw = response["body"].read().decode("utf-8")
            return _parse_bedrock_response(raw)
        except Exception as e_fallback:
            return (f"[ERROR] primary attempt failed: {e_primary} -- "
                    f"fallback attempt failed: {e_fallback}")




# ----------------- Example usage (for testing) -----------------
if __name__ == "__main__":
    print("Validating prompt...")
    user_q = "What is the rated power of the XR-220?"

    print("Querying KB and generating response...")
    raw_answer = generate_response(
        SYSTEM_PROMPT,
        user_q,
        model_id=MODEL_ID
    )

    # Optional pretty-print
    def extract_text_from_response(resp):
        try:
            return resp.get("message", {}).get("content", [])[0].get("text")
        except:
            return str(resp)

    print("Answer:\n", extract_text_from_response(raw_answer))

