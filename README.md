# DataDog Error Viewer

A simple Flask web application to track and manage DataDog test errors from CSV exports.

## Features

- 📊 **Error Dashboard**: View all test errors in a clean, organized table
- ✅ **Status Tracking**: Mark errors as addressed with checkboxes
- 💾 **Persistence**: Save addressed states to JSON file (survives page reloads)
- 📱 **Responsive Design**: Works on both desktop and mobile devices
- 🔍 **Error Details**: Click on error summaries to see full error messages
- 📈 **Progress Tracking**: Visual progress bar showing completion percentage
- 📄 **Pagination**: Navigate through large numbers of errors efficiently

## File Structure

```
datadog_viewer/
├── app.py                 # Main Flask application
├── pyproject.toml        # Project configuration and uv scripts
├── README.md             # This file
├── errors.csv            # Your DataDog error export (place here)
└── addressed_errors.json # Persistence file (created automatically)
```

## Setup

### Prerequisites

- Python 3.8 or higher
- uv package manager (recommended) or pip

### Installation

1. **Clone or navigate to the project directory:**
   ```bash
   cd datadog_viewer
   ```

2. **Install dependencies with uv:**
   ```bash
   uv sync
   ```

   Or with pip:
   ```bash
   pip install flask
   ```

3. **Place your CSV file:**
   - Copy your DataDog error export CSV file to the project directory
   - Rename it to `errors.csv` (or update the `CSV_FILE` variable in `app.py`)

## Running the Application

### Using uv (Recommended)

```bash
# Start the application
uv run start

# Or use the dev script
uv run dev
```

### Using Python directly

```bash
python app.py
```

### Using pip

```bash
# Install the package
pip install -e .

# Run the script
datadog-viewer
```

## Usage

1. **Start the application** using one of the methods above
2. **Open your browser** and navigate to `http://localhost:5000`
3. **View errors** in the organized table
4. **Mark errors as addressed** by checking the checkboxes
5. **View error details** by clicking on error summaries
6. **Track progress** using the statistics dashboard

## Configuration

You can modify the following variables in `app.py`:

- `CSV_FILE`: Path to your CSV file (default: "errors.csv")
- `PERSISTENCE_FILE`: Path to save addressed states (default: "addressed_errors.json")
- `PAGE_SIZE`: Number of errors to show per page (default: 50)

## API Endpoints

- `GET /`: Main page displaying errors
- `POST /api/toggle/<error_id>`: Toggle error addressed status
- `GET /api/stats`: Get current error statistics

## Data Format

The application expects a CSV file with the following structure:
- Column 1: Date/timestamp
- Column 2: JSON message containing test and error information

The JSON should have this structure:
```json
{
  "test": {
    "source": {"file": "path/to/test/file.py"},
    "name": "test_function_name"
  },
  "error": {
    "message": "Error message content"
  }
}
```

## Error Handling

- **CSV parsing errors**: Gracefully handled with warnings
- **JSON parsing errors**: Individual rows skipped with warnings
- **File I/O errors**: Proper error messages and fallbacks
- **Application context errors**: Automatically filtered out

## Customization

### Styling
The HTML template and CSS are embedded in the `app.py` file. You can modify:
- Colors and themes
- Layout and spacing
- Fonts and typography
- Responsive breakpoints

### Functionality
Extend the application by adding:
- Error filtering and search
- Export functionality
- User authentication
- Multiple CSV file support
- Error categorization

## Troubleshooting

### Common Issues

1. **CSV file not found**: Ensure `errors.csv` is in the project directory
2. **Permission errors**: Check file permissions for reading CSV and writing JSON
3. **Port already in use**: Change the port in `app.py` or stop other services
4. **Large CSV files**: The application loads the entire file into memory

### Debug Mode

The application runs in debug mode by default. To disable:
```python
app.run(debug=False, host='0.0.0.0', port=5000)
```

## Contributing

Feel free to submit issues, feature requests, or pull requests to improve the application.

## License

This project is open source and available under the MIT License.
