# Contributing to Postagent

Thank you for your interest in contributing to Postagent! This document provides guidelines and instructions for contributing to this human-in-the-loop LinkedIn automation agent.

## Getting Started

Postagent is a LinkedIn automation agent that uses local AI (Ollama/Llama 3.2) for draft generation from RSS feeds. The project is primarily written in Python (70.2%), with HTML templates (29.5%) and Docker configuration (0.3%).

### Prerequisites

- Python 3.x
- Ollama with Llama 3.2 model
- Docker (optional, for containerized deployment)
- Basic understanding of RSS feeds and LinkedIn automation

## How to Contribute

### Reporting Issues

- Use the GitHub issue tracker to report bugs or suggest features
- Check existing issues before creating a new one
- Provide detailed information including steps to reproduce bugs
- Include relevant system information and error messages

### Code Contributions

1. **Fork the Repository**
   - Fork the project to your GitHub account
   - Clone your fork locally

2. **Create a Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```
   or
   ```bash
   git checkout -b fix/your-bug-fix
   ```

3. **Make Your Changes**
   - Write clean, readable code
   - Follow existing code style and conventions
   - Add comments for complex logic
   - Update documentation as needed

4. **Test Your Changes**
   - Ensure your code works as expected
   - Test with Ollama/Llama 3.2 integration
   - Verify RSS feed processing
   - Check human-in-the-loop workflow

5. **Commit Your Changes**
   ```bash
   git commit -m "Brief description of your changes"
   ```
   - Use clear, descriptive commit messages
   - Reference issue numbers when applicable (e.g., "Fixes #123")

6. **Push to Your Fork**
   ```bash
   git push origin feature/your-feature-name
   ```

7. **Submit a Pull Request**
   - Open a PR from your fork to the main repository
   - Provide a clear description of the changes
   - Link related issues
   - Wait for review and address feedback

## Development Guidelines

### Python Code Style

- Follow PEP 8 style guidelines
- Use meaningful variable and function names
- Keep functions focused and modular
- Add docstrings to functions and classes

### HTML Templates

- Maintain semantic HTML structure
- Ensure templates are readable and well-formatted
- Comment complex template logic

### Ollama/AI Integration

- Test prompts thoroughly with Llama 3.2
- Document any prompt modifications
- Consider token limits and response times
- Ensure human-in-the-loop checkpoints are preserved

### RSS Feed Processing

- Handle various RSS feed formats
- Include error handling for feed parsing
- Document supported feed types

## Areas for Contribution

- **Ollama Prompt Customization**: Enhance prompt configuration options
- **RSS Feed Support**: Add support for more feed formats
- **UI Improvements**: Enhance the HTML interface
- **Documentation**: Improve setup guides and usage instructions
- **Testing**: Add unit tests and integration tests
- **Docker**: Optimize containerization
- **LinkedIn Integration**: Improve automation workflows
- **Error Handling**: Enhance error messages and recovery

## Questions?

If you have questions about contributing, feel free to:
- Open an issue with the `question` label
- Reach out to the maintainers

## License

By contributing to Postagent, you agree that your contributions will be licensed under the same license as the project.

Thank you for contributing! 🚀