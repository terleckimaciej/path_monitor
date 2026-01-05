# PathMonitor [still in dev]

PathMonitor is a Python-based tool for monitoring changes in specified folders. It supports configuration through Excel/CSV files and logs events in JSONL format.

## Features
- **Folder Monitoring**: Tracks file creation, modification, and deletion.
- **Configurable via Excel/CSV**: Define folder paths, include/exclude patterns, and other options.
- **Logging**: Outputs events in JSONL format for easy processing.
- **Observer Modes**: Supports `auto`, `polling`, and `auto-smart` modes for file system observation.

## Installation
1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd pathmonitor
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   .\.venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage
Run the program with the following command:
```bash
python -m app.cli --sheet-config <path-to-config.xlsx>
```
Works best when set to run with system startup via Task Scheduler. State logging is featured, so you won't loose anything.
### Arguments
- `--sheet-config`: Path to the Excel/CSV configuration file (required).
- `--observer`: Observer mode (`auto`, `polling`, `auto-smart`). Default is `auto-smart`.

## Configuration File
The configuration file should include the following columns:
- `path`: Folder path to monitor (required).
- `include`: Semicolon-separated patterns to include.
- `exclude`: Semicolon-separated patterns to exclude.
- `recursive`: Whether to monitor subdirectories (`true`/`false`).
- `observer`: Observer mode for the folder.
- `stabilize`: Whether to stabilize file events (`true`/`false`).
- `stabilize_seconds`: Time in seconds for stabilization.
- `log_csv`: Path to the log file.
- `state_path`: Path to the state file.

## License

This project is licensed under the MIT License.

