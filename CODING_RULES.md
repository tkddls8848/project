# CODING_RULES.md v2.0

## 1. Core Philosophy
- **KISS (Keep It Simple):** No excessive abstraction. "Clear 3 lines" > "Clever 1 line".
- **DRY (Don't Repeat):** Extract to `utils/` or `hooks/` upon the 2nd repetition (Rule of Three).
- **FP First (Functional):** Maintain immutability; prefer pure functions. Isolate side effects (I/O) to boundaries (Endpoint/Service).
- **Token Economy:** Optimize for LLM context windows. Minimize boilerplate, maximize semantic density.

## 2. Architecture & Directory
| Layer | Role | Directory (Example) |
|-------|------|---------------------|
| **Presentation** | UI Rendering, API Routing | `app/`, `components/` (Next), `routers/` (FastAPI) |
| **Application** | Business Use Case Flow | `hooks/` (Next), `services/` (FastAPI) |
| **Domain** | Core Logic, Pure Functions, Types | `types/`, `lib/core/` (Next), `schemas/` (FastAPI) |
| **Infrastructure** | DB, External APIs, LLM Calls | `lib/api/` (Next), `database/`, `llm/` (FastAPI) |

**Dependency Rule:** Lower layers (Domain) must not know about upper layers (Presentation).

## 3. Naming Conventions
| Category | TypeScript (Next.js) | Python (FastAPI) | JSON API |
|----------|----------------------|------------------|----------|
| **Variables/Functions** | `camelCase` | `snake_case` | `snake_case` |
| **Components/Classes** | `PascalCase` | `PascalCase` | N/A |
| **Files** | `kebab-case` (utils), `PascalCase` (Comp) | `snake_case` (All) | N/A |

**No-Mapper Rule:** Directly define and use the Backend's `snake_case` JSON response in Frontend Interfaces (Do not write conversion logic).

## 4. Type Safety
- **TS:** Strictly ban `any`. Define all Props/State/Responses with `interface`.
- **Py:** Mandatory Type Hints for all function arguments/returns. Validate external inputs with `Pydantic`.
- **Shared Types:** Maintain a single source of truth for cross-layer types in `types/` or `schemas/`.

## 5. Error Handling & Flow
- **Pattern:** Prefer `Result Pattern` (`{ success: boolean, data?, error? }`) over overuse of `try-catch` (for Internal Logic).
- **API Response:** Return appropriate HTTP Status Codes and standard error messages on exceptions.
- **Fallback:**
  1. Primary: Execute normal logic.
  2. Secondary: Graceful Degradation (reduced functionality).
  3. Tertiary: User-friendly error message.

## 6. LLM Integration Strategy
- **Prompt Engineering:** Do not hardcode prompts in code. Manage them in separate files/constants (`prompts/`).
- **Structured Output:** Enforce LLM responses as **JSON mode** or **Pydantic objects**, not raw text.
- **Parsimony:** Send only **core Schemas and metadata** as context to the LLM, not the entire code.
- **Validation Pipeline:** Always validate LLM outputs through schema validators before use.

## 7. Testing Priority
1. **Unit (60%):** Pure functions in Domain layer, business logic, utilities.
2. **Integration (30%):** API endpoint request/response testing.
3. **E2E (10%):** Verify core user scenarios (Happy Path) only.

## 8. Security & Best Practices
- **Input:** Assume "All external input is malicious" - Multi-layer validation with Pydantic/Zod.
- **Secrets:** Manage API Keys, etc., in `.env`. Never commit secrets to code.
- **Documentation:** Document "**Why** this was written this way" rather than "What this code does."

## 9. LLM-Optimized Coding Rules

### 9.1 Token Efficiency Principles
- **Minimal Comments:** Code should be self-documenting. Use comments only for non-obvious "why", not "what".
- **Import Consolidation:** Group related imports. Remove unused imports immediately.
- **No Dead Code:** Delete commented-out code blocks. Use version control instead.
- **Concise Naming:** Use clear but brief names (`getUserById` not `getSpecificUserByUniqueIdentifier`).

### 9.2 Context Window Management
- **File Size Limit:** Keep files under 300 lines. Split into modules at 250 lines.
- **Function Length:** Max 50 lines per function. Extract complex logic into sub-functions.
- **Dependency Graph:** Maintain shallow import trees (max 3 levels deep).
- **Anchor Points:** Use clear section markers for quick reference:
```typescript
  // === TYPES ===
  // === UTILITIES ===
  // === MAIN LOGIC ===
```

### 9.3 Change Management for Terminal Workflow
- **Atomic Changes:** One logical change per file edit (e.g., "Add validation" not "Refactor + Add feature").
- **Diff-Friendly:** Preserve line structure when possible. Avoid reformatting entire files.
- **Rollback Units:** Each change should be independently revertible.
- **Change Documentation:** Include brief change summary in commit-ready format:
```
  // CHANGE: Add email validation to User schema
  // REASON: Prevent invalid email submissions
```

### 9.4 LLM Response Validation Checklist
Before accepting LLM-generated code, verify:
1. **Syntax:** No syntax errors, proper indentation.
2. **Types:** All type annotations present and correct.
3. **Imports:** All imports declared and used.
4. **Consistency:** Follows project naming conventions.
5. **Completeness:** No placeholder comments like `// TODO: implement`.
6. **Security:** No hardcoded secrets or SQL injection risks.

## 10. Code Generation Workflow

### 10.1 Request Structure
When requesting code from LLM:
1. **Specify scope:** "Modify only `user-service.ts`" not "Fix the user system".
2. **Provide context:** Share relevant type definitions and function signatures.
3. **Define boundaries:** "Keep existing error handling pattern" or "Use existing `dbClient` instance".

### 10.2 Iterative Refinement
- **Start minimal:** Request core logic first, then add error handling, then optimization.
- **Verify incrementally:** Test each addition before requesting next feature.
- **Reject hallucinations:** If LLM invents non-existent functions/imports, regenerate with explicit constraints.

## 11. Anti-Patterns to Avoid

### 11.1 Token Waste
- Verbose error messages in code (use error codes + lookup table).
- Redundant type definitions (extract to shared types).
- Overly defensive programming (trust type system, validate at boundaries only).

### 11.2 Context Pollution
- Importing entire libraries when only using one function.
- Deeply nested object structures (flatten when possible).
- Mixing concerns in single file (separate UI/logic/data layers).

### 11.3 LLM Confusion Triggers
- Ambiguous variable names (`data`, `result`, `temp`).
- Inconsistent patterns across files.
- Missing intermediate types for complex transformations.

## 12. Quick Reference Card

### Before Writing Code
- [ ] Is this change atomic and focused?
- [ ] Do I have the minimum context loaded?
- [ ] Are types defined before implementation?

### During Code Review (Self)
- [ ] No `any` types in TypeScript?
- [ ] All functions have type hints in Python?
- [ ] Imports cleaned and organized?
- [ ] File under 300 lines?
- [ ] Functions under 50 lines?

### Before Committing
- [ ] No commented-out code?
- [ ] No hardcoded secrets?
- [ ] Change summary documented?
- [ ] Tests updated/added?

---

**Version:** 2.0  
**Last Updated:** 2026-01-01  
**Target:** LLM-assisted terminal-based development workflows