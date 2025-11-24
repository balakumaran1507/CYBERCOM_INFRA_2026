# Contributing to CYBERCOM CTF 2026

Thank you for your interest in contributing to CYBERCOM CTF 2026! We welcome contributions from the community to help improve and enhance this platform.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [How to Contribute](#how-to-contribute)
- [Development Guidelines](#development-guidelines)
- [Reporting Issues](#reporting-issues)
- [Security Vulnerabilities](#security-vulnerabilities)

---

## Code of Conduct

By participating in this project, you agree to maintain a respectful and collaborative environment. We expect all contributors to:

- Be respectful and inclusive
- Provide constructive feedback
- Focus on what is best for the community
- Show empathy towards other community members

---

## Getting Started

### Prerequisites

- **Docker** 20.10+ & **Docker Compose** 2.x
- **Python** 3.11+
- **Git**
- Basic understanding of Flask, SQLAlchemy, and Docker

### Setup Development Environment

1. **Fork the Repository**
   ```bash
   # Fork via GitHub UI, then clone your fork
   git clone https://github.com/YOUR_USERNAME/CYBERCOM_CTF_2026.git
   cd CYBERCOM_CTF_2026
   ```

2. **Add Upstream Remote**
   ```bash
   git remote add upstream https://github.com/balakumaran1507/CYBERCOM_CTF_2026.git
   ```

3. **Start Development Instance**
   ```bash
   docker compose up -d
   docker compose logs -f ctfd
   ```

4. **Access Platform**
   - Platform: http://localhost:8000
   - Complete initial setup wizard

---

## How to Contribute

### Reporting Bugs

**Found a bug?** Help us improve by reporting it:

1. **Search Existing Issues**: Check if the bug was already reported in [Issues](https://github.com/balakumaran1507/CYBERCOM_CTF_2026/issues)

2. **Open a New Issue** (if not found):
   - Use a clear, descriptive title
   - Describe the bug in detail
   - Include steps to reproduce
   - Specify your environment (OS, Docker version, browser, etc.)
   - Add screenshots if applicable

**Example Issue Title**: `[BUG] First Blood Not Awarded on Challenge Solve`

### Suggesting Enhancements

Have an idea for a new feature? We'd love to hear it!

1. **Search Existing Issues**: Check if your idea was already suggested
2. **Open a Feature Request**:
   - Describe the enhancement clearly
   - Explain why it would be valuable
   - Provide examples or mockups if possible

**Example Feature Title**: `[FEATURE] Add Challenge Category Filtering`

### Submitting Code Changes

#### 1. **Create a Feature Branch**

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b bugfix/your-bug-fix
```

**Branch Naming Conventions**:
- `feature/` - New features
- `bugfix/` - Bug fixes
- `security/` - Security patches
- `docs/` - Documentation updates
- `refactor/` - Code refactoring

#### 2. **Make Your Changes**

- Write clean, maintainable code
- Follow existing code style
- Add comments for complex logic
- Update documentation if needed

#### 3. **Test Your Changes**

```bash
# Run security validation tests
./redteam_execute_all.sh

# Test specific functionality
docker compose exec ctfd python your_test_script.py

# Verify Phase 2 initialization
docker compose logs ctfd | grep "PHASE2.*initialized successfully"
```

#### 4. **Commit Your Changes**

```bash
git add .
git commit -m "Add feature: Your feature description"
```

**Commit Message Guidelines**:
- Use present tense ("Add feature" not "Added feature")
- Use imperative mood ("Move cursor to..." not "Moves cursor to...")
- First line should be clear and concise (50 chars max)
- Include detailed description if needed

**Good commit messages**:
```
Add GDPR consent dashboard for admin panel

- Created new API endpoint /api/v1/phase2/consent
- Added admin template for consent management
- Includes user search and bulk consent operations
```

#### 5. **Push to Your Fork**

```bash
git push origin feature/your-feature-name
```

#### 6. **Open a Pull Request**

- Go to your fork on GitHub
- Click "New Pull Request"
- Select your branch
- Fill out the PR template with:
  - **Title**: Clear, descriptive summary
  - **Description**: What changed and why
  - **Testing**: How you tested the changes
  - **Related Issues**: Link to related issues (e.g., "Fixes #123")

---

## Development Guidelines

### Code Style

#### Python

- Follow **PEP 8** style guide
- Use **4 spaces** for indentation (no tabs)
- Maximum line length: **120 characters**
- Use descriptive variable names

**Good Example**:
```python
def calculate_suspicion_confidence(detected_patterns):
    """
    Calculate confidence score for flag sharing suspicion.

    Args:
        detected_patterns (list): List of detected pattern types

    Returns:
        float: Confidence score between 0.0 and 1.0
    """
    base_score = 0.5
    pattern_weights = {
        'same_ip': 0.15,
        'temporal_proximity': 0.10,
        'duplicate_wrong': 0.20
    }
    # ... implementation
```

#### JavaScript

- Use **ES6+** features where possible
- Use **camelCase** for variables and functions
- Use **2 spaces** for indentation
- Use **semicolons**

#### SQL

- Use **UPPERCASE** for SQL keywords
- Use **snake_case** for table and column names
- Include comments for complex queries

### Database Migrations

When adding new database tables or modifying existing ones:

1. Create a migration SQL file in `/migrations`
2. Use descriptive naming: `YYYYMMDD_feature_name.sql`
3. Include both `CREATE` and `DROP` statements
4. Test migration on fresh database

### Security Guidelines

- **Never commit secrets**: Use environment variables
- **Sanitize user input**: Always validate and sanitize
- **Use parameterized queries**: Prevent SQL injection
- **Follow GDPR compliance**: Respect user consent
- **Test security features**: Run red team scripts before submitting

**Example - Secure Query**:
```python
# ✅ GOOD (Parameterized)
results = db.session.execute(
    text("SELECT * FROM users WHERE id = :user_id"),
    {"user_id": user_id}
).fetchall()

# ❌ BAD (SQL Injection Risk)
results = db.session.execute(
    f"SELECT * FROM users WHERE id = {user_id}"
).fetchall()
```

### Testing Requirements

All significant changes should include tests:

- **Security Features**: Add red team attack script
- **API Endpoints**: Test all response codes
- **Database Operations**: Test CRUD operations
- **Edge Cases**: Test boundary conditions

### Documentation Requirements

Update documentation when:

- Adding new features
- Changing API endpoints
- Modifying configuration options
- Updating dependencies

**Files to Update**:
- `/docs/` - Technical documentation
- `README.md` - If user-facing changes
- Code comments - For complex logic

---

## Reporting Issues

### Bug Reports

Use the following template when reporting bugs:

```markdown
**Bug Description**
A clear and concise description of what the bug is.

**Steps to Reproduce**
1. Go to '...'
2. Click on '....'
3. See error

**Expected Behavior**
What you expected to happen.

**Actual Behavior**
What actually happened.

**Screenshots**
If applicable, add screenshots.

**Environment**
- OS: [e.g., Ubuntu 22.04]
- Docker Version: [e.g., 20.10.21]
- Browser: [e.g., Chrome 120]
- CYBERCOM Version: [e.g., Phase 2 v1.0]

**Additional Context**
Any other relevant information.
```

### Feature Requests

Use the following template:

```markdown
**Feature Description**
A clear and concise description of the feature.

**Use Case**
Describe why this feature would be valuable.

**Proposed Solution**
How you envision this feature working.

**Alternatives Considered**
Any alternative solutions you've thought about.

**Additional Context**
Mockups, examples, or references.
```

---

## Security Vulnerabilities

🔒 **CRITICAL**: Do **NOT** open public issues for security vulnerabilities.

If you discover a security vulnerability:

1. **Email**: security@cybercom-ctf.local
2. **Subject**: `[SECURITY] Brief description`
3. **Include**:
   - Vulnerability description
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

We take security seriously and will respond within 48 hours.

**Responsible Disclosure**:
- Allow us time to fix the issue before public disclosure
- We will credit you in our security advisory (if desired)
- See [SECURITY.md](SECURITY.md) for our full security policy

---

## Review Process

### Pull Request Review

All PRs will be reviewed for:

- **Code Quality**: Follows style guidelines
- **Functionality**: Works as intended
- **Security**: No vulnerabilities introduced
- **Testing**: Adequate test coverage
- **Documentation**: Properly documented

### Approval Process

1. **Automated Checks**: All CI/CD checks must pass
2. **Code Review**: At least one maintainer approval
3. **Testing**: Manual testing by reviewers
4. **Merge**: Maintainer merges when ready

### Status Checks

PRs must pass:
- ✅ Security validation tests
- ✅ Code linting (Flake8, Black)
- ✅ Database migration tests
- ✅ Phase 2 initialization tests

---

## Community

### Getting Help

Need help with development?

- **Documentation**: Check `/docs` directory
- **Issues**: Browse existing issues for solutions
- **Discussion**: Open a discussion issue for questions

### Recognition

Contributors will be recognized in:
- Project README
- Release notes
- Hall of Fame (for significant contributions)

---

## License

By contributing to CYBERCOM CTF 2026, you agree that your contributions will be licensed under the same license as the project (Apache License 2.0 for base components, proprietary for CYBERCOM customizations).

---

## Thank You!

Thank you for contributing to CYBERCOM CTF 2026. Your efforts help make this platform better for everyone in the CTF community!

---

**Questions?** Open a discussion issue or reach out to the maintainers.

**CYBERCOM CTF 2026** - Building the Future of CTF Competitions Together
