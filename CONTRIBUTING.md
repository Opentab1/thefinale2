# Contributing to Pulse 1.0

Thank you for your interest in contributing to Pulse! This document provides guidelines and instructions for contributing.

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help others learn and grow
- Follow the project's coding standards

## How to Contribute

### Reporting Bugs

1. Check if the bug has already been reported in [Issues](https://github.com/Opentab1/thefinale2/issues)
2. If not, create a new issue with:
   - Clear title and description
   - Steps to reproduce
   - Expected vs actual behavior
   - System information (Raspberry Pi model, OS version, etc.)
   - Relevant logs from `/var/log/pulse/`

### Suggesting Features

1. Open a new issue with the `feature request` label
2. Clearly describe the feature and its use case
3. Explain why it would benefit Pulse users
4. Provide examples if possible

### Pull Requests

1. **Fork the repository**
   ```bash
   git clone https://github.com/Opentab1/thefinale2.git
   cd pulse
   ```

2. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Make your changes**
   - Follow Python PEP 8 style guidelines
   - Add docstrings to functions and classes
   - Include type hints where appropriate
   - Write meaningful commit messages

4. **Test your changes**
   - Test on actual Raspberry Pi hardware if possible
   - Verify existing functionality still works
   - Test self-healing behavior (what happens if sensor fails?)

5. **Commit your changes**
   ```bash
   git add .
   git commit -m "Add: brief description of changes"
   ```

6. **Push to your fork**
   ```bash
   git push origin feature/your-feature-name
   ```

7. **Open a Pull Request**
   - Provide a clear description of changes
   - Reference any related issues
   - Include screenshots/videos for UI changes

## Development Setup

### Prerequisites
- Raspberry Pi 5 (recommended) or Pi 4
- Raspberry Pi OS (64-bit)
- Basic Python and JavaScript knowledge

### Local Development

```bash
# Set up Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Set up dashboard
cd dashboard/ui
npm install

# Run dashboard in development mode
npm run dev

# In another terminal, run the backend
cd dashboard/api
python3 server.py
```

## Project Structure

Key directories:
- `services/hub/` - Core orchestration logic
- `services/sensors/` - Sensor modules
- `services/controls/` - Smart home controllers
- `dashboard/api/` - Backend API
- `dashboard/ui/src/` - React frontend
- `bootstrap/wizard/` - First-boot setup

## Coding Guidelines

### Python

```python
def example_function(param1: str, param2: int) -> dict:
    """
    Brief description of what this function does.
    
    Args:
        param1: Description of param1
        param2: Description of param2
    
    Returns:
        Dictionary containing result
    """
    # Implementation
    pass
```

### React/JavaScript

```javascript
// Use functional components with hooks
function ComponentName({ prop1, prop2 }) {
  const [state, setState] = useState(initialValue)
  
  // Clear, descriptive function names
  const handleAction = () => {
    // Implementation
  }
  
  return (
    // JSX
  )
}

export default ComponentName
```

## Testing

### Manual Testing Checklist

- [ ] Installation completes without errors
- [ ] Setup wizard works correctly
- [ ] Dashboard loads and displays data
- [ ] All sensors report data correctly
- [ ] Control panels respond to input
- [ ] Auto mode functions as expected
- [ ] Manual mode works correctly
- [ ] System recovers from sensor failures
- [ ] Logs are created and readable

## Need Help?

- Check the [Wiki](https://github.com/Opentab1/thefinale2/wiki)
- Ask in [Discussions](https://github.com/Opentab1/thefinale2/discussions)
- Join our community chat (link TBD)

## Recognition

Contributors will be acknowledged in:
- CONTRIBUTORS.md file
- Release notes
- Project README

Thank you for making Pulse better! 🎵
