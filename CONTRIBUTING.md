# Contributing to YouTube Channel Crawler

Thank you for your interest in contributing to YouTube Channel Crawler! This document provides guidelines and instructions for contributing.

## 🌟 Ways to Contribute

- 🐛 Report bugs and issues
- 💡 Suggest new features or enhancements
- 📝 Improve documentation
- 🔧 Submit bug fixes
- ✨ Add new features
- 🧪 Write tests
- 🎨 Improve UI/UX

## 🚀 Getting Started

### Prerequisites

- Python 3.8 or higher
- Git
- Basic knowledge of FastAPI, SQLAlchemy, and JavaScript

### Setting Up Development Environment

1. **Fork the repository**
   ```bash
   # Click the "Fork" button on GitHub
   ```

2. **Clone your fork**
   ```bash
   git clone https://github.com/YOUR_USERNAME/youtube-crawler.git
   cd youtube-crawler
   ```

3. **Add upstream remote**
   ```bash
   git remote add upstream https://github.com/kenkenlee/youtube-crawler.git
   ```

4. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

5. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

6. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

7. **Run the application**
   ```bash
   python run.py
   ```

## 📋 Development Workflow

### 1. Create a Feature Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

Branch naming conventions:
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation updates
- `refactor/` - Code refactoring
- `test/` - Test additions or updates

### 2. Make Your Changes

- Write clean, readable code
- Follow existing code style and conventions
- Add comments for complex logic
- Update documentation as needed

### 3. Test Your Changes

```bash
# Run the application
python run.py

# Test manually through the web interface
# Visit http://127.0.0.1:5000

# Test API endpoints
# Visit http://127.0.0.1:5000/docs
```

### 4. Commit Your Changes

```bash
git add .
git commit -m "Brief description of changes"
```

**Commit Message Guidelines:**
- Use present tense ("Add feature" not "Added feature")
- Use imperative mood ("Move cursor to..." not "Moves cursor to...")
- First line should be 50 characters or less
- Reference issues and pull requests when relevant

Examples:
```
Add video download functionality
Fix summarization error for long transcripts
Update README with DeepSeek integration
Refactor crawler service for better performance
```

### 5. Push to Your Fork

```bash
git push origin feature/your-feature-name
```

### 6. Create a Pull Request

1. Go to your fork on GitHub
2. Click "New Pull Request"
3. Select your feature branch
4. Fill in the PR template with:
   - Description of changes
   - Related issues
   - Testing performed
   - Screenshots (if UI changes)

## 🎯 Code Style Guidelines

### Python Code

- Follow [PEP 8](https://pep8.org/) style guide
- Use type hints where appropriate
- Maximum line length: 100 characters
- Use meaningful variable and function names

**Example:**
```python
from typing import Optional, List
from sqlalchemy.orm import Session

def get_videos_by_channel(
    db: Session,
    channel_id: int,
    skip: int = 0,
    limit: int = 20
) -> List[Video]:
    """
    Retrieve videos for a specific channel.

    Args:
        db: Database session
        channel_id: Channel ID to filter by
        skip: Number of records to skip
        limit: Maximum number of records to return

    Returns:
        List of Video objects
    """
    return db.query(Video)\
        .filter(Video.channel_id == channel_id)\
        .offset(skip)\
        .limit(limit)\
        .all()
```

### JavaScript Code

- Use ES6+ features
- Use `const` and `let`, avoid `var`
- Use meaningful variable names
- Add comments for complex logic

**Example:**
```javascript
async function fetchVideos(channelId, page = 1) {
    try {
        const response = await fetch(`/api/videos?channel_id=${channelId}&page=${page}`);
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('Error fetching videos:', error);
        throw error;
    }
}
```

### HTML/CSS

- Use semantic HTML5 elements
- Follow Bootstrap conventions
- Keep CSS organized and commented
- Use responsive design principles

## 🧪 Testing Guidelines

### Manual Testing Checklist

Before submitting a PR, test:

- [ ] Application starts without errors
- [ ] All pages load correctly
- [ ] Can add/edit/delete channels
- [ ] Can start and monitor crawl sessions
- [ ] Videos are displayed correctly
- [ ] Summarization works (if applicable)
- [ ] WebSocket updates work in real-time
- [ ] No console errors in browser
- [ ] Responsive design works on mobile

### API Testing

Use the Swagger UI at `/docs` to test API endpoints:

1. Test all modified endpoints
2. Verify request/response formats
3. Check error handling
4. Test edge cases

## 📝 Documentation

### Code Documentation

- Add docstrings to all functions and classes
- Document parameters, return values, and exceptions
- Include usage examples for complex functions

### README Updates

Update README.md when:
- Adding new features
- Changing configuration options
- Modifying installation steps
- Adding new dependencies

## 🐛 Reporting Bugs

### Before Reporting

1. Check if the bug has already been reported
2. Verify it's reproducible
3. Test with the latest version

### Bug Report Template

```markdown
**Description**
Clear description of the bug

**Steps to Reproduce**
1. Go to '...'
2. Click on '...'
3. See error

**Expected Behavior**
What should happen

**Actual Behavior**
What actually happens

**Environment**
- OS: [e.g., Windows 10, Ubuntu 20.04]
- Python Version: [e.g., 3.9.5]
- Browser: [e.g., Chrome 96]

**Screenshots**
If applicable

**Additional Context**
Any other relevant information
```

## 💡 Feature Requests

### Feature Request Template

```markdown
**Feature Description**
Clear description of the feature

**Use Case**
Why is this feature needed?

**Proposed Solution**
How should it work?

**Alternatives Considered**
Other approaches you've thought about

**Additional Context**
Mockups, examples, etc.
```

## 🔍 Code Review Process

### What We Look For

- **Functionality**: Does it work as intended?
- **Code Quality**: Is it clean and maintainable?
- **Performance**: Is it efficient?
- **Security**: Are there any vulnerabilities?
- **Documentation**: Is it well-documented?
- **Testing**: Has it been tested?

### Review Timeline

- Initial review: Within 3-5 days
- Follow-up reviews: Within 2-3 days
- Merge: After approval from maintainers

## 📜 License

By contributing, you agree that your contributions will be licensed under the MIT License.

## 🤝 Code of Conduct

### Our Standards

- Be respectful and inclusive
- Accept constructive criticism
- Focus on what's best for the community
- Show empathy towards others

### Unacceptable Behavior

- Harassment or discrimination
- Trolling or insulting comments
- Personal or political attacks
- Publishing others' private information

## 📞 Getting Help

- **Questions**: Open a GitHub Discussion
- **Bugs**: Open a GitHub Issue
- **Security**: Email maintainers directly

## 🎉 Recognition

Contributors will be:
- Listed in the project's contributors page
- Mentioned in release notes
- Credited in documentation

Thank you for contributing to YouTube Channel Crawler! 🚀
