# CLAUDE.md - AI Assistant Guide for organizer-api

> **Last Updated**: 2026-03-02
> **Project Status**: New Project - Initial Setup Phase
> **Primary Branch**: TBD (main/master)
> **Development Branch Pattern**: `claude/*`

---

## Project Overview

**organizer-api** is a new project being developed to provide API services for an organization/task management system. As this is a greenfield project, this document will evolve as the codebase develops.

### Project Goals
- Build a robust, scalable API for task/project organization
- Maintain clean architecture and code quality
- Follow best practices for API development
- Ensure comprehensive testing and documentation

---

## Repository Status

### Current State
- **Status**: Empty repository, no code yet
- **Branch**: `claude/add-claude-documentation-R1OIl`
- **Next Steps**: Determine technology stack and initialize project structure

---

## Development Conventions for AI Assistants

### Branch Naming
- **Feature branches**: `claude/<descriptive-name>-<session-id>`
- **Critical**: All branch names must start with `claude/` and end with matching session ID
- **Example**: `claude/add-user-auth-XYZ123`

### Git Workflow

#### Commits
- Use clear, descriptive commit messages in present tense
- Format: `<type>: <description>`
- Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `style`
- Examples:
  - `feat: add user authentication endpoints`
  - `fix: resolve database connection timeout`
  - `docs: update API documentation`

#### Push Operations
- **Always use**: `git push -u origin <branch-name>`
- **Critical**: Branch must start with `claude/` and end with session ID
- **Retry logic**: If network errors occur, retry up to 4 times with exponential backoff (2s, 4s, 8s, 16s)
- **Never force push** to main/master branches

#### Pull/Fetch Operations
- Prefer specific branch fetches: `git fetch origin <branch-name>`
- Use retry logic for network failures (same as push)
- Pull format: `git pull origin <branch-name>`

### Code Quality Standards

#### General Principles
1. **Read before modifying**: Always read existing code before making changes
2. **Avoid over-engineering**: Only implement what's requested
3. **No premature abstraction**: Don't create utilities for one-time operations
4. **Security first**: Prevent injection attacks, XSS, and OWASP top 10 vulnerabilities
5. **Simple solutions**: Three similar lines > premature abstraction
6. **Clean deletions**: Remove unused code completely, no `_vars` or `// removed` comments

#### What NOT to Do
- Don't add unrequested features or refactoring
- Don't add comments/docstrings to unchanged code
- Don't add error handling for impossible scenarios
- Don't design for hypothetical future requirements
- Don't use backwards-compatibility hacks
- Don't create abstractions before they're needed

### Testing Standards
- Write tests for new features and bug fixes
- Maintain existing test coverage
- Run full test suite before committing
- Fix failing tests immediately

---

## Project Structure (To Be Established)

### Recommended Structure
When initializing this project, consider the following structure:

```
organizer-api/
├── src/
│   ├── api/              # API routes and controllers
│   ├── models/           # Data models/schemas
│   ├── services/         # Business logic
│   ├── middleware/       # Custom middleware
│   ├── utils/            # Utility functions
│   ├── config/           # Configuration files
│   └── index.ts/js       # Application entry point
├── tests/
│   ├── unit/            # Unit tests
│   ├── integration/     # Integration tests
│   └── fixtures/        # Test data
├── docs/                # Documentation
├── .env.example         # Environment variables template
├── .gitignore          # Git ignore rules
├── package.json        # Dependencies (if Node.js)
├── tsconfig.json       # TypeScript config (if applicable)
└── README.md           # Project documentation
```

---

## Technology Stack (To Be Decided)

### Considerations for Stack Selection
When choosing technologies, consider:

1. **Backend Framework**:
   - Node.js + Express/Fastify (JavaScript/TypeScript)
   - Python + FastAPI/Flask
   - Go + Gin/Echo
   - Rust + Actix/Axum

2. **Database**:
   - PostgreSQL (relational, robust)
   - MongoDB (document-based)
   - SQLite (lightweight, development)

3. **ORM/Query Builder**:
   - Prisma (Node.js/TypeScript)
   - SQLAlchemy (Python)
   - GORM (Go)

4. **Authentication**:
   - JWT tokens
   - OAuth 2.0
   - Session-based

5. **Testing**:
   - Jest/Vitest (JavaScript/TypeScript)
   - Pytest (Python)
   - Go testing package

---

## API Design Principles

### RESTful Conventions
- Use proper HTTP methods: GET, POST, PUT/PATCH, DELETE
- Use meaningful resource names (plural nouns)
- Use proper status codes:
  - 200: Success
  - 201: Created
  - 400: Bad Request
  - 401: Unauthorized
  - 403: Forbidden
  - 404: Not Found
  - 500: Internal Server Error

### Endpoint Structure
```
GET    /api/v1/tasks          # List all tasks
GET    /api/v1/tasks/:id      # Get specific task
POST   /api/v1/tasks          # Create new task
PUT    /api/v1/tasks/:id      # Update task
DELETE /api/v1/tasks/:id      # Delete task
```

### Response Format
```json
{
  "success": true,
  "data": { ... },
  "message": "Operation successful",
  "timestamp": "2026-01-23T12:00:00Z"
}
```

### Error Response Format
```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable message",
    "details": { ... }
  },
  "timestamp": "2026-01-23T12:00:00Z"
}
```

---

## Security Best Practices

### Critical Security Measures
1. **Input Validation**: Validate and sanitize all user inputs
2. **SQL Injection**: Use parameterized queries/ORM
3. **XSS Prevention**: Escape output, use Content Security Policy
4. **Authentication**: Implement secure token management
5. **Authorization**: Check permissions for all operations
6. **Rate Limiting**: Prevent abuse with rate limits
7. **CORS**: Configure properly for production
8. **Environment Variables**: Never commit secrets (.env in .gitignore)
9. **HTTPS**: Use TLS in production
10. **Dependencies**: Keep dependencies updated, scan for vulnerabilities

### Files to Never Commit
- `.env` (environment variables)
- `credentials.json`
- API keys or secrets
- Database dumps with sensitive data
- Private keys

---

## Development Workflow

### Setting Up Development Environment
1. Clone repository
2. Install dependencies
3. Copy `.env.example` to `.env`
4. Configure local database
5. Run migrations (if applicable)
6. Start development server
7. Run tests to verify setup

### Before Committing
1. **Read** all changed files
2. **Test** changes thoroughly
3. **Lint** code (if linter configured)
4. **Review** for security issues
5. **Update** documentation if needed
6. **Stage** only relevant files (avoid `git add .` with secrets)
7. **Commit** with descriptive message
8. **Push** to feature branch

### Creating Pull Requests
1. Ensure all tests pass
2. Review all changes in diff
3. Write clear PR description:
   - Summary of changes (1-3 bullet points)
   - Test plan (checklist of testing steps)
   - Link to related issues
4. Include session URL in PR body
5. Use `gh pr create` for consistency

---

## Task Management for AI Assistants

### Using TodoWrite Tool
- **Always** use TodoWrite for multi-step tasks (3+ steps)
- **Update** status in real-time (pending → in_progress → completed)
- **Mark completed** immediately after finishing each task
- **Keep one task** in_progress at a time
- **Break down** complex tasks into smaller steps

### Task Completion Criteria
Mark tasks completed ONLY when:
- Implementation is fully complete
- Tests are passing
- No blocking errors remain
- All requirements are met

### When to Use TodoWrite
- Complex multi-step implementations
- User provides multiple tasks
- Non-trivial features requiring planning
- After receiving new instructions

---

## File Operation Guidelines

### Reading Files
- Use `Read` tool instead of `cat`, `head`, `tail`
- Read files before modifying them
- Read in parallel when possible for multiple independent files

### Editing Files
- Use `Edit` tool instead of `sed`, `awk`
- Preserve exact indentation from original file
- Make surgical changes, don't over-edit
- Use `replace_all` for variable renaming

### Writing Files
- Use `Write` tool instead of `echo >` or `cat <<EOF`
- Prefer editing existing files over creating new ones
- Only create files when absolutely necessary
- Don't create markdown files unless requested

### Searching Code
- Use `Grep` tool instead of bash `grep` or `rg`
- Use `Glob` tool for file pattern matching
- Use `Task` with `Explore` agent for open-ended searches
- Search in parallel when multiple independent searches needed

---

## Communication Guidelines

### Tone and Style
- Be concise and professional
- No emojis unless user requests them
- No time estimates or predictions
- Focus on facts and problem-solving
- Use technical accuracy over validation
- GitHub-flavored markdown for formatting

### Code References
- Include file path and line numbers: `file.ts:123`
- Example: "The error occurs in `src/api/routes.ts:45`"

### Outputting Information
- Output text directly to communicate
- NEVER use `echo` or comments to communicate
- All communication outside tool use is shown to user

---

## Testing Strategy

### Test Coverage Goals
- Unit tests for business logic
- Integration tests for API endpoints
- End-to-end tests for critical workflows
- Minimum 80% code coverage target

### Test Organization
```
tests/
├── unit/
│   ├── services/
│   ├── models/
│   └── utils/
├── integration/
│   └── api/
└── fixtures/
    └── test-data.json
```

### Testing Best Practices
- Test behavior, not implementation
- Use descriptive test names
- Keep tests isolated and independent
- Mock external dependencies
- Test edge cases and error scenarios

---

## Documentation Standards

### Code Documentation
- Document complex logic and algorithms
- Explain "why" not "what" in comments
- Keep comments up-to-date with code changes
- Don't comment obvious code

### API Documentation
- Document all endpoints
- Include request/response examples
- List required/optional parameters
- Document error responses
- Use OpenAPI/Swagger if possible

### Project Documentation
- Keep README.md updated
- Document setup and installation
- Include usage examples
- Maintain changelog
- Update this CLAUDE.md as project evolves

---

## Common Patterns and Conventions

### Error Handling
```javascript
// Example pattern (adjust for chosen stack)
try {
  const result = await service.performOperation();
  return { success: true, data: result };
} catch (error) {
  logger.error('Operation failed', { error });
  throw new ApiError('Operation failed', 500);
}
```

### Validation
- Validate at system boundaries (user input, external APIs)
- Don't validate internal function calls
- Use validation libraries (Zod, Joi, etc.)
- Return clear validation error messages

### Logging
- Log at appropriate levels (debug, info, warn, error)
- Include context in log messages
- Don't log sensitive information
- Use structured logging in production

---

## Environment Configuration

### Environment Variables Template
```env
# Server Configuration
PORT=3000
NODE_ENV=development

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/organizer
DATABASE_POOL_SIZE=10

# Authentication
JWT_SECRET=your-secret-key-here
JWT_EXPIRY=7d

# External Services
API_KEY=your-api-key-here

# Logging
LOG_LEVEL=info
```

### Configuration Management
- Use `.env` for local development
- Use secure secret management in production
- Validate required environment variables on startup
- Provide sensible defaults where appropriate

---

## Deployment Considerations

### Pre-Deployment Checklist
- [ ] All tests passing
- [ ] Security scan completed
- [ ] Dependencies updated
- [ ] Environment variables configured
- [ ] Database migrations applied
- [ ] Documentation updated
- [ ] Monitoring configured
- [ ] Backup strategy in place

### Production Settings
- Enable HTTPS/TLS
- Configure CORS properly
- Set secure headers
- Enable rate limiting
- Configure logging and monitoring
- Set up error tracking (Sentry, etc.)
- Configure auto-scaling if needed

---

## Troubleshooting Common Issues

### Git Push Failures
- **403 Error**: Check branch name starts with `claude/` and ends with session ID
- **Network Error**: Retry with exponential backoff (2s, 4s, 8s, 16s)
- **Rejected**: Pull latest changes and rebase if needed

### Development Issues
- **Port in use**: Check for running processes, change PORT in .env
- **Database connection**: Verify DATABASE_URL and database is running
- **Module not found**: Run dependency installation command
- **Test failures**: Review test output, check for environment issues
- **Server not running**: The dev server is not persistent. Start it with:
  ```bash
  ANTHROPIC_AUTH_TOKEN=$(cat /home/claude/.claude/remote/.session_ingress_token) uvicorn src.main:app --host 0.0.0.0 --port 8000
  ```
  Always check `curl http://localhost:8000/health` before making API calls.

### Known Gotchas in `src/api/agent.py`
- `_todo_read` constructs `TodoRead` **manually** from a SQLAlchemy model — it does NOT use `from_attributes` auto-mapping.
- Any new field added to the `TodoRead` schema must also be explicitly added to `_todo_read`. Omitting a field causes a Pydantic validation error on every agent call that touches a todo.

---

## Resources and Links

### Project Links
- Repository: (TBD)
- Documentation: (TBD)
- Issue Tracker: (TBD)
- CI/CD Pipeline: (TBD)

### Useful References
- RESTful API Design: https://restfulapi.net/
- OWASP Top 10: https://owasp.org/www-project-top-ten/
- Semantic Versioning: https://semver.org/
- Conventional Commits: https://www.conventionalcommits.org/

---

## Maintaining This Document

### When to Update CLAUDE.md
- Technology stack is chosen/changed
- New architectural decisions are made
- New conventions are established
- Project structure changes significantly
- New tools or workflows are adopted
- Security practices are updated

### Update Protocol
1. Read current version completely
2. Make necessary updates
3. Update "Last Updated" date at top
4. Update "Project Status" if changed
5. Commit with message: `docs: update CLAUDE.md with <changes>`

---

## Next Steps for Project Initialization

### Immediate Tasks
1. **Decide technology stack** (Language, framework, database)
2. **Initialize project structure** (Create directories, config files)
3. **Set up development environment** (Dependencies, local setup)
4. **Configure git ignore** (Add .env, node_modules, etc.)
5. **Create README.md** (Project overview, setup instructions)
6. **Set up testing framework** (Choose and configure test runner)
7. **Initialize database** (Choose DB, create schema/migrations)
8. **Create first API endpoint** (Health check or basic endpoint)
9. **Set up CI/CD** (GitHub Actions, tests automation)
10. **Update this document** (Add specific stack details)

### Questions to Answer
- What is the primary use case for this organizer API?
- Who are the target users?
- What features are MVP (minimum viable product)?
- What are the performance requirements?
- What are the security requirements?
- What is the expected scale?
- What is the deployment target (cloud provider, self-hosted)?

---

## Example Implementation Checklist

When implementing a new feature, follow this checklist:

- [ ] Read and understand existing related code
- [ ] Create feature branch with proper naming
- [ ] Plan implementation with TodoWrite (if complex)
- [ ] Write failing tests first (TDD approach)
- [ ] Implement minimum necessary code
- [ ] Make tests pass
- [ ] Handle errors appropriately
- [ ] Add input validation
- [ ] Check for security vulnerabilities
- [ ] Update documentation if needed
- [ ] Run full test suite
- [ ] Review changes for quality
- [ ] Commit with descriptive message
- [ ] Push to feature branch
- [ ] Create pull request with summary and test plan

---

**Remember**: This document is a living guide. As the project grows and evolves, keep this documentation updated to reflect the current state and best practices of the organizer-api project.
