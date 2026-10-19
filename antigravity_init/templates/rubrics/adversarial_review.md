# Adversarial Code Review Rubric & Failure Mode Taxonomy

This rubric provides an adversarial evaluation checklist grounded in state-of-the-art research on LLM coding failures. Reviewers must rigorously interrogate changes using these categories.

---

## 1. Sycophancy Detection
LLMs exhibit a strong tendency to validate peer subagents and user propositions uncritically, praising changes while overlooking critical structural defects.
- [ ] **Uncritical Acceptance Check:** Did the review approve the PR without scrutinizing edge-case claims or validating assumptions against actual execution?
- [ ] **Rubber-Stamping Detection:** Are there positive assertions ("looks good", "well-structured") without citing specific line numbers and verification command output?
- [ ] **Independent Invariant Verification:** Did the reviewer independently test or re-derive assertions rather than trusting the implementer's self-assessment?

---

## 2. Boundary Bug Catalog
Off-by-one errors, empty collections, path resolution subtleties, and boundary conditions that LLMs frequently miscalculate.
- [ ] **Empty and Boundary Inputs:** Are empty strings, empty lists, `None` values, and zero-length buffers handled gracefully without crashing?
- [ ] **Worktree and Path Edge Cases:** Are path manipulations safe against symlinks, relative paths, missing parent directories, and git worktrees (e.g., `.git` as a file rather than a directory)?
- [ ] **Off-By-One & Range Boundaries:** Are slicing operations, index offsets, and loop boundaries inclusive/exclusive as specified?
- [ ] **Concurrency & Re-entrancy:** Are shared resources or file writes safe against race conditions or partial writes?

---

## 3. Test Mock Leakage
Mocks that over-simplify behavior, mock the wrong layers, or allow tests to pass while runtime production code is broken.
- [ ] **Over-Mocked Units:** Are tests mocking internal units to the point where real behavior is never tested against actual runtime components?
- [ ] **Mock State Leakage:** Do mocks persist state between test cases or fail to clean up environment variables and monkeypatches?
- [ ] **Tautological Assertions:** Are test assertions checking mock return values rather than inspecting observable system side effects?
- [ ] **External Dependency Parity:** Do mocked interfaces accurately mimic standard library or external system behaviors (including error codes and exceptions)?

---

## 4. Hallucinated Imports & APIs
APIs, modules, or functions that do not exist or are not available in the target runtime environment.
- [ ] **Zero Third-Party Dependency Rule:** Are all imports strictly from the Python standard library without implicit pip package expectations?
- [ ] **Python Version Compatibility:** Are APIs compatible with Python >= 3.9 (avoiding APIs introduced in 3.10+ unless guarded)?
- [ ] **Non-Existent Attribute Calls:** Are all module functions and methods verified against official standard library documentation?
- [ ] **Shadowed Standard Names:** Does any module or variable shadow standard library module names?

---

## 5. Untested Failure Branches & Error Handling
Code that assumes the happy path and fails catastrophically or silently suppresses critical errors.
- [ ] **Subprocess & IO Error Traps:** Are subprocess failures, network disconnects, file permissions, and timeouts properly caught and handled?
- [ ] **Silent Exception Swallowing:** Are bare `except:` clauses or `except Exception: pass` used to hide defects?
- [ ] **Idempotence & Recovery:** Can the operation be safely re-run multiple times after a mid-execution failure without corrupting state?
