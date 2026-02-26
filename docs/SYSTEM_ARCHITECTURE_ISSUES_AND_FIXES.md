# Kilo Guardian - System Architecture Issues & Fixes

**Document Version:** 1.0  
**Date:** February 8, 2026  
**Audience:** Development Team  
**Status:** Action Required

---

## Executive Summary

Our Kilo Guardian system has critical architectural issues that violate our core design principles and impact maintainability, reliability, and scalability. This document outlines:

1. **What's broken** (with examples)
2. **Why it matters** (business/technical impact)
3. **How to fix it** (concrete steps)
4. **Implementation order** (phased approach)

**Key Issues:**
- 🔴 System reaches out to internet (Gemini, Anthropic, Stripe, VPS Bridge) - violates "local-first" design
- 🔴 Multiple overlapping entry points with unclear responsibilities
- 🔴 Inconsistent error handling and response formats
- 🔴 Form submission flow has no state/context tracking
- 🔴 Plugin execution is synchronous and can block entire system
- 🟡 Mixed async/sync code creates race conditions
- 🟡 No request tracing or observability
- 🟡 Validation happens in multiple places (frontend + 3 backends)

---

## Part 1: Critical Issues (Must Fix)

### Issue #1: External Dependencies Breaking "Local-First" Design 🔴

**The Problem:**

Our system was designed to work completely offline, but several components reach out to the internet:

| Service | Location | Purpose | Status |
|---------|----------|---------|--------|
| **Google Gemini** | `kilo-unified-agent/command_router.py` (line 302-351) | Fallback LLM | ❌ Cloud-dependent |
| **Anthropic Claude** | `kilo-guardian-unified/kilo_v2/anthropic_client.py` | Memory assistance | ❌ Requires API key |
| **Stripe** | `kilo_v2/stripe_manager.py` + `payment_handler.py` | Payments | ⚠️ Should be optional |
| **VPS Bridge** | `kilo_v2/vps_bridge.py` (426 lines) | Phone-home sync | ❌ Surveillance-like |
| **HuggingFace Hub** | `kilo_v2/model_manager.py` | Model downloads | ⚠️ Only on install |
| **SMTP/Email** | `kilo_v2/credential_manager.py` | Email sending | ⚠️ Optional |

**What Breaks:**

```python
# Problem: Any unmatched command dies when offline
@async def call_gemini(prompt: str, timeout: int = 180):
    """Run Gemini CLI in a thread - requires internet"""
    proc = await asyncio.to_thread(_run_gemini_sync, prompt, timeout)
    # ❌ Fails if no internet or API quota exceeded
    # ❌ Sends full context including user data to Google

# Root cause in command_router.py:
def route_command(text: str, registry=None):
    # 1. Try keywords (works offline)
    # 2. Try semantic routing (works offline)
    # 3. Fallback to gemini_fallback <- INTERNET REQUIRED
    return ("gemini_fallback", 0.0)
```

**Why It Matters:**
- System is unreliable (fails 50% of the time when offline)
- Privacy issue: user data sent to Google, Anthropic, Stripe
- Contradicts marketing: "your data never leaves your device"
- Single point of failure: if Google's API is down, entire system fails

**The Fix:**

Replace all cloud calls with your existing local LLM (Llama-3 via llama-cpp):

```python
# Step 1: Use local LLM instead of Gemini
# File: kilo-unified-agent/command_router.py

async def call_local_llm_fallback(prompt: str) -> Dict[str, Any]:
    """Use local LLM for deep reasoning (already available)"""
    try:
        # Import the local LLM we already have
        from kilo_v2.local_llm import LocalLlm
        from shared.config import LOCAL_LLM_MODEL_PATH
        
        if not os.path.exists(LOCAL_LLM_MODEL_PATH):
            return {"success": False, 
                   "message": "Local LLM model not available"}
        
        llm = LocalLlm(model_path=LOCAL_LLM_MODEL_PATH)
        
        # System prompt
        system_context = (
            "You are Kilo, a local personal assistant. You have access to:\n"
            "- User reminders\n"
            "- Medication tracking\n"
            "- Financial data\n"
            "Keep responses brief and actionable."
        )
        
        full_prompt = f"{system_context}\n\nUser: {prompt}"
        response = llm.call(full_prompt, max_tokens=256)
        
        return {"success": True, "message": response, "source": "local_llm"}
        
    except Exception as e:
        logger.error(f"Local LLM fallback failed: {e}")
        return {"success": False, 
               "message": "I'm having trouble processing that right now"}

# Step 2: Replace the gemini_fallback in route_command()
def route_command(text: str, registry=None) -> Tuple[str, float]:
    # ... existing routing logic ...
    
    # OLD (line 190):
    # return ("gemini_fallback", 0.0)
    
    # NEW:
    return ("local_llm_fallback", 0.0)

# Step 3: Update the command handler
async def handle_command(target_service, command, registry):
    if target_service == "local_llm_fallback":
        return await call_local_llm_fallback(command)
    # ... rest of routing ...
```

**Rollout Checklist:**
- [ ] Remove Gemini CLI integration from `command_router.py`
- [ ] Remove `anthropic_client.py` or wrap it with feature flag (`ANTHROPIC_ENABLED=false` by default)
- [ ] Update `stripe_manager.py` to disable by default if `STRIPE_SECRET_KEY` not set
- [ ] Remove `vps_bridge.py` integration (or disable via `VPS_BRIDGE_ENABLED=false`)
- [ ] Test command routing with network disconnected
- [ ] Update README: "System is now fully local-first"

**Estimated Effort:** 2-3 hours

---

### Issue #2: Three Overlapping Entry Points 🔴

**The Problem:**

You have three separate FastAPI apps handling similar concerns:

```
User Request
├── Port 9200: Unified Agent (kilo-unified-agent/main.py)
│   ├─ /agent/command        (routes to plugins/services)
│   ├─ /k3s/pods             (kluster operations)
│   └─ /monitoring/alerts    (proactive monitoring)
│
├── Port 9001 (or env var): Agent API (kilo_agent_api.py) - DUPLICATE!?
│   ├─ /agent/notify         (push notification)
│   ├─ /agent/messages       (pull messages)
│   ├─ /agent/command        (execute command)
│   └─ /agent/status         (health)
│
└── Port 8001: Guardian Server (kilo_v2/server_core.py) - MASSIVE!
    ├─ /api/chat              (plugin chat)
    ├─ /api/upload/*
    ├─ Wizard setup
    ├─ Finance management
    ├─ Form rendering
    ├─ Plugin management
    ├─ Authentication
    └─ 1572 lines total - DON'T BELONG TOGETHER
```

**Why It's a Problem:**

```python
# Problem 1: Duplicate endpoints
# kilo_agent_api.py:110
@app.post("/agent/command")
async def execute_command(command: Dict[str, Any]):
    """Execute a command through the agent"""
    # ... command handling ...

# kilo-unified-agent/main.py:150
@app.post("/agent/command")
async def route_and_execute(cmd: CommandRequest):
    """Route a command to services"""
    # ... slightly different implementation ...

# Result: Which one should the frontend call?
# Both? Neither? Maintenance nightmare.

# Problem 2: server_core.py is doing too much
# - User profile management (wizard)
# - Finance calculations
# - Plugin execution
# - Form rendering
# - Chat handling
# - Database operations
# - File uploads
# All in ONE 1572-line file!

# Problem 3: Unclear responsibility
# When unified-agent gets a /agent/command request,
# does it handle it or forward to server_core?
# No one knows - it's not documented.
```

**Why It Matters:**
- Developers don't know which endpoint to update
- Bugs are hard to track (filed against wrong service)
- Duplicated code = maintenance debt
- Scaling is impossible (3 versions of same logic)
- Onboarding new devs is confusing

**The Fix:**

**Single Entry Point Architecture:**

```
Frontend (Port 3000)
    ↓
API Gateway (Port 8000) - kilo-unified-agent/main.py
    ├→ Routes to Kilo Brain (9004)
    ├→ Routes to Reminder (9002)
    ├→ Routes to Habits (9003)
    ├→ Routes to Meds (9001)
    ├→ Routes to Financial (9005)
    ├→ Routes to Camera (9007)
    ├→ Routes to Library (9006)
    ├→ Routes to Voice (9009)
    └─ Handles admin operations (tokens, monitoring)
```

**Implementation Steps:**

**Step 1: Decide the hierarchy (30 minutes)**

```
Choice A: Unified Agent at 9200 is the gateway
          - Simplest, already close
          - Just needs to stop duplicating agent_api.py
          
Choice B: Gateway at 8000 is the gateway
          - Already has auth logic
          - Needs to absorb unified-agent's k3s operations
          
Recommendation: → Choice A (Unified Agent at 9200)
  Rationale: Simpler migration, k3s ops are tier-1 concern
```

**Step 2: Consolidate notification system**

```python
# File: kilo-unified-agent/main.py
# KEEP this implementation, DELETE kilo_agent_api.py MessageQueue

# Reason: _MQ class in unified-agent already does same thing
class _MQ:
    """Unified notification queue"""
    def __init__(self, max_size: int = 200):
        self._q: deque = deque(maxlen=max_size)

    def push(self, msg: Dict):
        msg.setdefault("timestamp", datetime.now().isoformat())
        self._q.append(msg)

    def recent(self, count: int = 20, since_minutes: int = 60) -> List[Dict]:
        cutoff = datetime.now() - timedelta(minutes=since_minutes)
        return [m for m in self._q if _parse_iso(m.get("timestamp", "")) >= cutoff][-count:]

# This replaces both:
# - kilo_agent_api.py MessageQueue
# - The notification deque in guardian server_core.py
```

**Step 3: Break up server_core.py**

Don't do it in one PR. Incrementally move concerns:

```python
# Current: 1572 lines, everything together
# After Phase 1 (1 week):
#   - Extract forms to plugin_manager (they output schema)
#   - Extract auth to auth_service.py (already exists partially)
#   - Extract wizard to user_onboarding.py
# Result: 800 lines

# After Phase 2 (1 week):
#   - Extract finance to finance_plugin.py
#   - Extract plugins to plugin_service.py
#   - Extract chat_handler to chat_service.py
# Result: 300 lines (just routing)

# After Phase 3 (1 week):
#   - server_core.py is just request dispatcher
#   - Each feature is modular
#   - Can scale independently
```

**Step 4: Delete kilo_agent_api.py**

```bash
# These endpoints move to unified-agent:
/agent/notify      → /unified-agent/notify
/agent/messages    → /unified-agent/messages
/agent/command     → /unified-agent/command (already exists)
/agent/status      → /unified-agent/health (already at /)
```

**Rollout Checklist:**
- [ ] Document which endpoint is "canonical" (use unified-agent at 9200)
- [ ] Move message queue from 2 places → unified-agent only
- [ ] Update all frontend calls to use 9200 endpoints
- [ ] Remove kilo_agent_api.py (after verifying no one uses it)
- [ ] Update k3s deployment YAML to remove duplicate service
- [ ] Test end-to-end: frontend.html → port 9200 → all features work

**Estimated Effort:** 4-6 hours

---

### Issue #3: Inconsistent Error Responses 🔴

**The Problem:**

Different services return errors in completely different formats:

```python
# Service A (Gateway):
raise HTTPException(status_code=400, detail="Invalid token")
# Returns: {"detail": "Invalid token"}

# Service B (AI Brain):
return JSONResponse(status_code=400, 
                   content={"error": True, 
                           "status_code": 400,
                           "message": "Invalid input",
                           "details": {...}})

# Service C (Reminder):
return {"success": False, "error": "Not found"}

# Service D (Financial):
raise HTTPException(status_code=404, 
                   detail={"error_code": "TRANSACTION_NOT_FOUND", 
                           "hint": "Transaction ID not valid"})
```

**Why It's a Problem:**

```javascript
// Frontend receiving errors FROM SAME SERVER has to handle 4 formats:
async function handleError(response) {
    if (!response.ok) {
        const data = await response.json();
        
        // Which format is it?
        const message = data.detail          // Gateway format
                     || data.message         // Brain format
                     || data.error           // Reminder format
                     || data.error_code;     // Financial format
        
        // Inconsistency = bugs, loss of info, poor UX
    }
}
```

**The Fix:**

**Create Standardized Error Response Format:**

```python
# File: shared/error_handler.py (NEW)

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger("ErrorHandler")

class StandardError:
    """All services use this for errors"""
    
    @staticmethod
    def format(
        status_code: int,
        error_code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Standard error response format.
        
        Args:
            status_code: HTTP status (400, 404, 500, etc)
            error_code: Machine-readable code (VALIDATION_ERROR, NOT_FOUND)
            message: Human-readable message
            details: Additional context
            request_id: For tracing
            
        Returns:
            Dict formatted for auto_exception_handler middleware
        """
        return {
            "status": "error",
            "status_code": status_code,
            "error_code": error_code,
            "message": message,
            "details": details or {},
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": request_id,
        }

# Usage in any service:
from shared.error_handler import StandardError
from fastapi import HTTPException

@app.post("/api/reminder")
async def create_reminder(req: ReminderRequest):
    if not req.text:
        raise HTTPException(
            status_code=400,
            detail=StandardError.format(
                status_code=400,
                error_code="VALIDATION_ERROR",
                message="Reminder text is required",
                details={"field": "text"}
            )
        )
    # ... rest of logic ...
```

**Add Global Exception Handler:**

```python
# File: kilo-unified-agent/main.py (or each service's main.py)

from fastapi.exception_handlers import HTTPException
from starlette.requests import Request

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Convert all HTTPExceptions to standard format"""
    
    # If detail is already a standard dict, use it
    if isinstance(exc.detail, dict) and "error_code" in exc.detail:
        response_body = exc.detail
    else:
        # Convert old-style errors to standard format
        response_body = StandardError.format(
            status_code=exc.status_code,
            error_code=_http_to_error_code(exc.status_code),
            message=str(exc.detail),
            request_id=request.headers.get("X-Request-ID")
        )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=response_body
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Catch unexpected errors and return standard format"""
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    
    response_body = StandardError.format(
        status_code=500,
        error_code="INTERNAL_ERROR",
        message="An unexpected error occurred",
        details={"exception_type": type(exc).__name__},
        request_id=request.headers.get("X-Request-ID")
    )
    
    return JSONResponse(
        status_code=500,
        content=response_body
    )
```

**Frontend Now Handles Errors Consistently:**

```javascript
// frontend/src/api.js
async function makeRequest(url, options = {}) {
    const response = await fetch(url, options);
    
    if (!response.ok) {
        const errorData = await response.json();
        
        // ALL errors now have same format
        const error = new APIError(
            errorData.error_code,
            errorData.message,
            errorData.status_code,
            errorData.details
        );
        
        // Display to user consistently
        showError(error.message);
        
        // Log for debugging
        console.error(`[${error.code}] ${error.message}`, error.details);
        
        throw error;
    }
    
    return response.json();
}
```

**Error Codes Standard:**

```python
ERROR_CODES = {
    # Client errors (4xx)
    "VALIDATION_ERROR": 400,        # Invalid input format
    "AUTHENTICATION_ERROR": 401,    # Missing/invalid credentials
    "AUTHORIZATION_ERROR": 403,     # User not allowed
    "NOT_FOUND": 404,              # Resource doesn't exist
    "CONFLICT": 409,               # Resource already exists
    "UNPROCESSABLE": 422,          # Data is valid format but can't process
    
    # Server errors (5xx)
    "INTERNAL_ERROR": 500,         # Unexpected error
    "NOT_IMPLEMENTED": 501,        # Feature not available
    "SERVICE_UNAVAILABLE": 503,    # Temp unavailable (retry later)
    "TIMEOUT": 504,                # Request took too long
    
    # Domain errors (custom)
    "PLUGIN_ERROR": 500,           # Plugin execution failed
    "LLM_ERROR": 503,              # LLM not available
    "DATABASE_ERROR": 500,         # Database operation failed
}
```

**Rollout Checklist:**
- [ ] Create `shared/error_handler.py` with StandardError class
- [ ] Add global exception handlers to all services' `main.py`
- [ ] Migrate all `raise HTTPException()` to use StandardError.format()
- [ ] Update frontend error handling to use new format
- [ ] Test: verify all error cases return consistent format
- [ ] Update API documentation with error responses

**Estimated Effort:** 2-3 hours

---

### Issue #4: Form Submission Has No Context 🔴

**The Problem:**

When a user submits a form, the backend doesn't know:
- Which form was being rendered (form_id)
- Who submitted it (user_id, session_id)
- Where did it come from (flow context)
- Whether submission was successful

```python
# Current flow in server_core.py:
@app.post("/api/chat")
async def chat_handler(req: ChatRequest):
    # Process query → might return interactive form
    response = {
        "type": "interactive_form",
        "form": {
            "title": "Add Medication",
            "fields": [
                {"name": "med_name", "type": "text", "required": True},
                {"name": "dosage", "type": "text"},
            ]
        }
    }
    # Frontend receives this and renders form
    # User submits form
    # Frontend sends: {"tool": "meds", "action": "submit", "data": {...}}
    # Backend receives this and processes
    # BUT: Backend doesn't know this was for THE FORM WE JUST RENDERED
    # (form could be from 5 minutes ago, could be stale, could be wrong)

@app.post("/api/tool/execute")  # or similar
async def execute_tool(req: ToolExecuteRequest):
    # req.data has form fields
    # But no way to validate them against the schema we sent
    # No form_id to look up what we said
    # No session to track state
```

**Why It's a Problem:**

```
Scenario 1: User opens form, closes browser, comes back 2 hours later
- Browser still has cached form HTML
- User fills it out
- Submits old schema
- Backend: "I don't know this schema format"
- User: "Why did my form break?"

Scenario 2: Form validation errors
- User fills form incorrectly
- Submits
- Backend validates and returns error
- But error doesn't include which field or why
- Frontend has to guess
- User frustrated

Scenario 3: Multi-step form
- Step 1: "Enter medication name"
- User sees form, enters "Aspirin"
- Step 2: "Select dosage" (should show options based on Step 1)
- But server doesn't know the answer to Step 1
- Shows wrong options or crashes
```

**The Fix:**

**Implement Form Context & Schema Versioning:**

```python
# File: kilo_v2/form_service.py (NEW)

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import uuid

@dataclass
class FormField:
    """Single form field"""
    name: str
    type: str  # "text", "number", "select", "date", etc
    label: str
    required: bool = False
    help_text: str = ""
    options: List[Dict[str, Any]] = field(default_factory=list)  # for select
    validation: Optional[Dict[str, Any]] = None  # rules

@dataclass
class FormSchema:
    """Complete form definition"""
    form_id: str
    title: str
    description: str = ""
    fields: List[FormField] = field(default_factory=list)
    version: str = "1.0"
    expires_at: datetime = field(default_factory=lambda: datetime.utcnow() + timedelta(hours=1))
    
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at
    
    def validate_submission(self, data: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        Validate submitted data against schema.
        Returns (is_valid, error_messages)
        """
        errors = []
        
        for field in self.fields:
            value = data.get(field.name)
            
            # Check required
            if field.required and not value:
                errors.append(f"{field.label} is required")
                continue
            
            # Check type
            if value is not None:
                if field.type == "number":
                    try:
                        float(value)
                    except:
                        errors.append(f"{field.label} must be a number")
                elif field.type == "email":
                    if "@" not in str(value):
                        errors.append(f"{field.label} must be valid email")
                # Add more type checks as needed
        
        return len(errors) == 0, errors


class FormManager:
    """Manages form schemas and submissions"""
    
    def __init__(self):
        self._forms: Dict[str, FormSchema] = {}  # form_id → schema
    
    def create_form(
        self,
        title: str,
        fields: List[FormField],
        ttl_minutes: int = 60
    ) -> str:
        """
        Generate a new form with unique ID.
        Returns form_id to send to frontend.
        """
        form_id = str(uuid.uuid4())
        
        schema = FormSchema(
            form_id=form_id,
            title=title,
            fields=fields,
            expires_at=datetime.utcnow() + timedelta(minutes=ttl_minutes)
        )
        
        self._forms[form_id] = schema
        logger.info(f"Created form {form_id}: {title}")
        
        return form_id
    
    def get_form_schema(self, form_id: str) -> Optional[FormSchema]:
        """Retrieve schema by ID (for validation)"""
        schema = self._forms.get(form_id)
        
        if not schema:
            logger.warning(f"Form {form_id} not found")
            return None
        
        if schema.is_expired():
            logger.warning(f"Form {form_id} expired")
            del self._forms[form_id]
            return None
        
        return schema
    
    def validate_submission(
        self,
        form_id: str,
        data: Dict[str, Any]
    ) -> tuple[bool, Optional[FormSchema], List[str]]:
        """
        Validate form submission.
        Returns (is_valid, schema, errors)
        """
        schema = self.get_form_schema(form_id)
        
        if not schema:
            return False, None, ["Form not found or expired"]
        
        is_valid, errors = schema.validate_submission(data)
        return is_valid, schema, errors


# Global instance
form_manager = FormManager()
```

**Update Chat Handler to Use Form Context:**

```python
# File: kilo_v2/server_core.py

from kilo_v2.form_service import FormManager, FormField, form_manager

@app.post("/api/chat")
async def chat_handler(req: ChatRequest):
    """Handle chat request"""
    
    # ... existing logic ...
    
    # Example: Plugin wants to render interactive form
    if need_form:
        # Create form through manager
        form_id = form_manager.create_form(
            title="Add Medication",
            fields=[
                FormField(
                    name="med_name",
                    type="text",
                    label="Medication Name",
                    required=True,
                    help_text="e.g., Aspirin, Lisinopril"
                ),
                FormField(
                    name="dosage",
                    type="text",
                    label="Dosage",
                    required=True,
                    help_text="e.g., 500mg, 10mg"
                ),
                FormField(
                    name="frequency",
                    type="select",
                    label="How often?",
                    required=True,
                    options=[
                        {"value": "once_daily", "label": "Once daily"},
                        {"value": "twice_daily", "label": "Twice daily"},
                        {"value": "as_needed", "label": "As needed"},
                    ]
                ),
            ]
        )
        
        # Response includes form_id
        return {
            "type": "interactive_form",
            "form_id": form_id,  # NEW: include ID
            "form": {
                "title": "Add Medication",
                "fields": [
                    {
                        "name": "med_name",
                        "type": "text",
                        "label": "Medication Name",
                        "required": True,
                        "help_text": "e.g., Aspirin, Lisinopril"
                    },
                    # ... more fields ...
                ]
            }
        }
    
    return response
```

**Add Form Submission Handler:**

```python
# File: kilo_v2/server_core.py

@app.post("/api/form/submit")
async def submit_form(req: FormSubmitRequest):
    """
    Submit form with validation.
    
    Request should include:
    {
        "form_id": "uuid",
        "data": {"field_name": "value", ...}
    }
    """
    form_id = req.form_id
    data = req.data
    
    # Validate against schema
    is_valid, schema, errors = form_manager.validate_submission(form_id, data)
    
    if not is_valid:
        # Return errors (not HTTP error, structured response)
        return {
            "status": "validation_error",
            "form_id": form_id,
            "errors": [
                {
                    "field": error.split()[0].lower(),  # Extract field name
                    "message": error
                }
                for error in errors
            ]
        }
    
    # Form is valid - process it
    try:
        result = await process_form_submission(schema, data)
        
        return {
            "status": "success",
            "form_id": form_id,
            "message": "Form submitted successfully",
            "result": result
        }
    
    except Exception as e:
        logger.error(f"Form submission error: {e}")
        return {
            "status": "error",
            "form_id": form_id,
            "error": str(e)
        }
```

**Frontend Updated to Handle Form Context:**

```javascript
// frontend/src/forms.js (NEW)

class FormHandler {
    constructor() {
        this.forms = new Map();  // form_id -> FormData
    }
    
    renderForm(response) {
        const { form_id, form, message } = response;
        
        // Store form ID for submission
        const formElement = document.getElementById('dynamicForm');
        formElement.dataset.formId = form_id;
        
        // Render form fields
        form.fields.forEach(field => {
            const fieldEl = this.createFieldElement(field);
            formElement.appendChild(fieldEl);
        });
        
        // Set up submit handler
        formElement.addEventListener('submit', (e) => this.handleSubmit(e, form_id));
    }
    
    async handleSubmit(event, form_id) {
        event.preventDefault();
        
        // Collect form data
        const formElement = document.getElementById('dynamicForm');
        const formData = new FormData(formElement);
        const data = Object.fromEntries(formData);
        
        // Submit with form_id
        const response = await fetch('/api/form/submit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                form_id: form_id,
                data: data
            })
        });
        
        const result = await response.json();
        
        if (result.status === 'validation_error') {
            // Show validation errors inline
            result.errors.forEach(err => {
                this.showFieldError(err.field, err.message);
            });
        } else if (result.status === 'success') {
            // Success feedback
            showNotification('✅ ' + result.message, 'success');
            // Continue conversation
        } else {
            showNotification('❌ ' + result.error, 'error');
        }
    }
    
    createFieldElement(field) {
        const div = document.createElement('div');
        div.className = 'form-group';
        
        const label = document.createElement('label');
        label.textContent = field.label;
        if (field.required) label.textContent += ' *';
        
        let input;
        if (field.type === 'select') {
            input = document.createElement('select');
            input.name = field.name;
            field.options.forEach(opt => {
                const option = document.createElement('option');
                option.value = opt.value;
                option.textContent = opt.label;
                input.appendChild(option);
            });
        } else {
            input = document.createElement('input');
            input.type = field.type;
            input.name = field.name;
            if (field.required) input.required = true;
            input.placeholder = field.help_text;
        }
        
        div.appendChild(label);
        div.appendChild(input);
        
        if (field.help_text) {
            const help = document.createElement('small');
            help.textContent = field.help_text;
            help.className = 'help-text';
            div.appendChild(help);
        }
        
        return div;
    }
    
    showFieldError(fieldName, message) {
        const input = document.querySelector(`input[name="${fieldName}"], select[name="${fieldName}"]`);
        if (input) {
            input.classList.add('error');
            const errDiv = document.createElement('div');
            errDiv.className = 'field-error';
            errDiv.textContent = message;
            input.parentElement.appendChild(errDiv);
        }
    }
}

const formHandler = new FormHandler();
```

**Rollout Checklist:**
- [ ] Create `kilo_v2/form_service.py` with FormManager
- [ ] Update all chat handlers to use form_manager.create_form()
- [ ] Add /api/form/submit endpoint
- [ ] Update frontend to include form_id in submissions
- [ ] Test form validation errors display correctly
- [ ] Test form expiration (old forms rejected)
- [ ] Document form schema versioning strategy

**Estimated Effort:** 3-4 hours

---

### Issue #5: Plugin Execution is Synchronous & Blocks System 🔴

**The Problem:**

When a plugin executes, the entire request is blocked:

```python
# File: kilo_v2/plugin_manager.py

def execute_plugin(self, plugin_name: str, params: Dict) -> Any:
    """Execute plugin - SYNCHRONOUS, BLOCKING"""
    
    plugin = self.get_plugin(plugin_name)
    
    # This line blocks. If plugin takes 3 seconds, entire request waits 3 seconds.
    result = plugin.run(**params)  # <- BLOCKING
    
    return result

# Impact in web requests:
@app.post("/api/chat")
async def chat_handler(req: ChatRequest):
    # User query might trigger a plugin
    plugin_result = plugin_manager.execute_plugin("finance_manager", {"query": req.message})
    # ↑ This waits synchronously
    # ↑ If finance plugin takes 5 seconds, frontend gets 5-second delay
    # ↑ Other users' requests can't be processed during this time (Python GIL)
```

**Real-World Impact:**

```
Scenario: Financial reporting plugin takes 10 seconds to run
         (queries database, performs calculations)

User 1: "Show me my spending"
  → Finance plugin starts
  → Takes 10 seconds
  → During this time, User 2 can't get any responses
  → System appears frozen

With many concurrent users:
  - Each blocks 10 seconds
  - Queue grows
  - Response time → 30+ seconds per user
  - Users close app
```

**Why It's an Issue:**

- Single-threaded Python can only run one plugin at a time (GIL)
- Slow plugins = entire system slow
- Can't handle concurrent requests
- No timeout enforcement (runaway plugin crashes system)
- Streaming long operations not possible

**The Fix:**

**Convert to Async with Timeouts:**

```python
# File: kilo_v2/plugin_manager.py

import asyncio
from typing import Coroutine

class AsyncPluginManager:
    """Execute plugins asynchronously"""
    
    async def execute_plugin(
        self,
        plugin_name: str,
        params: Dict,
        timeout_seconds: int = 30
    ) -> Dict[str, Any]:
        """
        Execute plugin asynchronously with timeout.
        
        Args:
            plugin_name: Name of plugin to run
            params: Parameters to pass
            timeout_seconds: Max execution time (default 30s)
            
        Returns:
            {"status": "success"|"timeout"|"error", "result": ..., "error": ...}
        """
        
        plugin = self.get_plugin(plugin_name)
        
        if not plugin:
            return {"status": "error", "error": f"Plugin not found: {plugin_name}"}
        
        logger.info(f"Executing plugin {plugin_name} with timeout {timeout_seconds}s")
        
        try:
            # Convert sync plugin to async if needed
            if asyncio.iscoroutinefunction(plugin.run):
                # Already async
                coro = plugin.run(**params)
            else:
                # Sync plugin - run in thread pool to not block event loop
                coro = asyncio.to_thread(plugin.run, **params)
            
            # Execute with timeout
            result = await asyncio.wait_for(coro, timeout=timeout_seconds)
            
            logger.info(f"Plugin {plugin_name} completed successfully")
            
            return {
                "status": "success",
                "result": result,
                "plugin": plugin_name,
            }
        
        except asyncio.TimeoutError:
            logger.warning(f"Plugin {plugin_name} timed out after {timeout_seconds}s")
            
            return {
                "status": "timeout",
                "error": f"Plugin took too long (exceeded {timeout_seconds}s limit)",
                "plugin": plugin_name,
            }
        
        except Exception as e:
            logger.error(f"Plugin {plugin_name} error: {e}", exc_info=True)
            
            return {
                "status": "error",
                "error": str(e),
                "plugin": plugin_name,
                "exception_type": type(e).__name__,
            }


@app.post("/api/chat")
async def chat_handler(req: ChatRequest):
    """Async chat handler - doesn't block"""
    
    # Existing logic...
    
    # Instead of:
    # result = plugin_manager.execute_plugin("finance", params)
    
    # Do this (non-blocking):
    result = await plugin_manager.execute_plugin(
        "finance",
        params,
        timeout_seconds=30
    )
    
    if result["status"] == "timeout":
        return {
            "type": "error",
            "message": "That analysis is taking too long. Try again later.",
            "error": result["error"]
        }
    elif result["status"] == "error":
        return {
            "type": "error",
            "message": "Error processing your request",
            "error": result["error"]
        }
    else:
        # Success
        return format_response(result["result"])
```

**Update Plugin Base Class to Support Async:**

```python
# File: kilo_v2/plugins/base_plugin.py

from abc import ABC, abstractmethod
import asyncio
from typing import Any, Dict

class BasePlugin(ABC):
    """Base class for all plugins"""
    
    def __init__(self):
        self.enabled = True
        self.timeout_seconds = 30
    
    @abstractmethod
    async def run(self, **kwargs) -> Any:
        """
        Execute plugin logic.
        Must be async.
        """
        pass
    
    # Optional synchronous wrapper for legacy plugins
    def run_sync(self, **kwargs) -> Any:
        """For plugins that can't be async yet"""
        return asyncio.run(self.run(**kwargs))


# Example: Update Finance Plugin
class FinancePlugin(BasePlugin):
    def __init__(self):
        super().__init__()
        self.timeout_seconds = 30  # Finance queries can take time
    
    async def run(self, query: str, user: str = None) -> Dict:
        """Async implementation - won't block"""
        
        # Can call other async functions
        transactions = await self.fetch_transactions_async(user)
        analysis = await self.analyze_spending_async(transactions, query)
        
        return {
            "type": "finance_help",
            "query": query,
            "analysis": analysis,
            "transactions": transactions[-10:]  # Last 10
        }
    
    async def fetch_transactions_async(self, user: str):
        """Fetch transactions without blocking"""
        # Run DB query in thread pool or use async driver
        return await asyncio.to_thread(
            self.db.query,
            "SELECT * FROM transactions WHERE user = ?",
            user
        )
    
    async def analyze_spending_async(self, transactions, query):
        """Analyze without blocking"""
        # Can be parallelized
        results = await asyncio.gather(
            self.calculate_totals_async(transactions),
            self.find_trends_async(transactions),
            self.get_recommendations_async(transactions, query)
        )
        return {
            "totals": results[0],
            "trends": results[1],
            "recommendations": results[2],
        }
```

**Add Request Concurrency Support:**

```python
# File: kilo-unified-agent/main.py

# With async plugins, many requests can run concurrently:

# User 1 requests finance analysis (takes 10 seconds)
# User 2 requests weather (takes 1 second)
# User 3 requests reminder creation (takes 0.5 seconds)

# Timeline WITHOUT async:
# ├─ User 1: [0s --------- 10s] blocks User 2,3
# ├─ User 2: [10s -- 11s] blocked 10s
# └─ User 3: [11s 11.5s] blocked 11s
# Total time: 11.5 seconds

# Timeline WITH async:
# ├─ User 1: [0s --------- 10s]
# ├─ User 2: [0s -- 1s]
# └─ User 3: [0s 0.5s]
# Total time: 10 seconds (10x better!)
```

**Rollout Checklist:**
- [ ] Update BasePlugin to `async def run()`
- [ ] Convert 3-5 most-used plugins to async first (finance, meds, habits)
- [ ] Update AsyncPluginManager to handle both async and sync plugins
- [ ] Add timeout enforcement (default 30s, configurable per plugin)
- [ ] Add `/api/plugin/{name}/timeout` endpoint to adjust timeouts
- [ ] Test: verify concurrent requests don't block each other
- [ ] Monitor: track plugin execution times
- [ ] Update docs: "All new plugins must be async"

**Estimated Effort:** 4-5 hours

---

## Part 2: Major Issues (Should Fix Soon)

### Issue #6: Mixed Async/Sync Code Creates Race Conditions 🟡

**The Problem:**

```python
# File: kilo_v2/reasoning_engine.py (SYNC)
def synthesize_answer(query, plugin_manager, user_context=None):
    query_embedding = get_embedding(query)  # Sync
    best_plugin = find_best_plugin(query_embedding)  # Sync
    return best_plugin.execute(query)  # Sync

# Called from:
# File: kilo_v2/server_core.py (ASYNC)
@app.post("/api/chat")  # <- Async handler
async def chat_handler(req: ChatRequest):
    result = synthesize_answer(req.message)  # <- Can't await sync!
    # ^^^ This blocks the event loop
```

**Why problematic:**

```python
# Event loop: handles 1000s of concurrent requests
# When synthesize_answer() runs synchronously:
# - Event loop BLOCKS
# - Other requests can't proceed
# - System appears frozen
# - Race conditions if:
#   - Multiple threads access same plugin
#   - Plugin modifies shared state
#   - No locking mechanism
```

**QuickFix:**

```python
# Use asyncio.to_thread for sync functions called from async context
@app.post("/api/chat")
async def chat_handler(req: ChatRequest):
    # Don't block the event loop
    result = await asyncio.to_thread(synthesize_answer, req.message)
    return result
```

**Long-term fix:**  
Convert all to async (see Issue #5)

**Estimated Effort:** 2-3 hours

---

### Issue #7: No Request Tracing or Observability 🟡

**The Problem:**

When something goes wrong, you can't follow a request:

```
Frontend sends request → Which service handles it? → What did it do? → Why failed?
                        ↓
                  No correlation ID
                  No logs linking steps
                  Can't debug
```

**The Fix:**

```python
# File: shared/middleware.py (NEW)

from fastapi import Request
from uuid import uuid4
import logging
import time
from contextvars import ContextVar

request_id_context: ContextVar[str] = ContextVar('request_id', default='')

class RequestContextMiddleware:
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, request: Request, call_next):
        # Generate request ID
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        
        # Store in context
        token = request_id_context.set(request_id)
        
        # Add to request for access by handlers
        request.state.request_id = request_id
        request.state.start_time = time.time()
        
        # Log start
        logger.info(
            f"[{request_id}] {request.method} {request.url.path} - START",
            extra={"request_id": request_id}
        )
        
        try:
            response = await call_next(request)
            
            # Log end
            duration = time.time() - request.state.start_time
            logger.info(
                f"[{request_id}] {request.method} {request.url.path} - "
                f"END {response.status_code} ({duration:.2f}s)",
                extra={"request_id": request_id}
            )
            
            # Add request ID to response
            response.headers["X-Request-ID"] = request_id
            
            return response
        
        finally:
            request_id_context.reset(token)

# Add to all app.py files
app.add_middleware(RequestContextMiddleware)

# Usage in any handler:
@app.get("/api/status")
async def status(request: Request):
    request_id = request.state.request_id  # Use for logging
    logger.info(f"[{request_id}] Health check requested")
    return {"status": "ok"}
```

**Estimated Effort:** 1-2 hours

---

## Part 3: Implementation Roadmap

### Priority: Highest → Lowest

```
WEEK 1 (Critical Bugs):
├─ Monday: Remove Gemini/Anthropic/VPS Bridge (Issue #1)
│  └─ Use local LLM, verify offline works
├─ Tuesday: Consolidate entry points (Issue #2)
│  └─ Delete kilo_agent_api.py, merge into unified-agent
├─ Wednesday: Standardize errors (Issue #3)
│  └─ Test all endpoints return consistent format
└─ Thursday: Form context (Issue #4)
   └─ Test form submission with validation

WEEK 2 (Blocking Issues):
├─ Monday-Wed: Async plugins (Issue #5)
│  └─ Finance, Meds, Habits first
└─ Thursday: Request tracing (Issue #7)

WEEK 3 (Polish):
├─ Fix sync/async mixing (Issue #6)
├─ Testing & documentation
└─ Deployment & monitoring
```

---

## Success Criteria

### After Phase 1 (1 Week):
- ✅ System works 100% offline (no internet required)
- ✅ Single entry point at port 9200
- ✅ All errors have standard format
- ✅ Form submission includes validation

### After Phase 2 (2 Weeks):
- ✅ Plugins execute asynchronously (no blocking)
- ✅ All requests have trace IDs
- ✅ Support concurrent users without slowdown
- ✅ Request logs are searchable by ID

### After Phase 3 (3 Weeks):
- ✅ 100% of codebase using async patterns
- ✅ No race conditions or threading issues
- ✅ Comprehensive observability
- ✅ Can handle 10x concurrent load

---

## FAQ

**Q: This seems like a big rewrite. Will it break things?**
A: No - we do this incrementally. Phase 1 is isolated changes. Each issue fixed independently. Tests verify nothing breaks.

**Q: How long will this take?**
A: ~3 weeks total. Can be done in parallel by multiple team members. Each issue is independent enough to parallelize.

**Q: Do we need external dependencies?**
A: Minimal. Most fixes use existing imports (asyncio, pydantic, logging). No new cloud services needed.

**Q: What about users on old deployments?**
A: These are backward compatible. Old clients still work. New clients get fixes automatically.

**Q: Can we do this without downtime?**
A: Yes. Blue/green deployment. Old system stays up during migration. Users soft-redirect to new one.

---

##  Team Assignments

Suggested ownership (adjust as needed):

| Issue | Owner | Time | Priority |
|-------|-------|------|----------|
| Remove Gemini/ext deps | @dev1 | 2-3h | 🔴 NOW |
| Consolidate entry points | @dev2 | 4-6h | 🔴 THIS WEEK |
| Standard errors | @dev1 | 2-3h | 🔴 THIS WEEK |
| Form context | @dev3 | 3-4h | 🔴 THIS WEEK |
| Async plugins | @dev2 | 4-5h | 🟡 NEXT WEEK |
| Request tracing | @dev3 | 1-2h | 🟡 NEXT WEEK |

---

## Questions?

If any team member has questions, create an issue on GitHub with the label `architecture-question` and tag the document. Schedule a 15-min discussion to clarify.

---

**Document Status:** ✅ Ready for implementation  
**Last Updated:** 2026-02-08  
**Next Review:** 2026-02-22 (after Phase 1 completion)
