---
name: commit
description: Use when the user wants to create a git commit
modes: [code, debug]
---

## Instructions

When creating a git commit:

1. Run `git status` to see all changes
2. Run `git diff --staged` to review staged changes
3. If nothing is staged, ask the user what to stage or suggest staging relevant files
4. Draft a concise commit message following conventional commits format:
   - `feat:` for new features
   - `fix:` for bug fixes
   - `refactor:` for code restructuring
   - `docs:` for documentation
   - `test:` for tests
   - `chore:` for maintenance
5. Show the proposed commit message and ask for confirmation
6. Execute `git commit -m "<message>"`
7. Show the result
