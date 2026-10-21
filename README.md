# MCP Browser Agent

An MCP (Model Context Protocol) server that enables AI assistants to automate browser-based tasks, extract structured web data, download files, and organize local outputs using Python.

The project integrates **FastMCP**, **browser-use**, and **Playwright** to provide browser automation tools to compatible MCP clients such as Cursor and Claude Desktop.

> **Project status:** In development. Features and setup instructions may change as the implementation evolves.

## Features

- **MCP integration:** Expose browser automation capabilities as tools that compatible AI clients can discover and invoke.
- **AI-powered browsing:** Use a browser agent to navigate websites and perform multi-step tasks.
- **Structured data extraction:** Collect useful information and return results in a structured format.
- **File downloads:** Save supported downloads to a designated local workspace.
- **File organization:** Move generated or downloaded files into categorized directories.
- **Python-based architecture:** Keep server, browser automation, configuration, and file management in separate modules.
- **Extensible design:** Add more tools and integrations as the project grows.

## Architecture

```text
┌──────────────────────────────┐
│        MCP Client            │
│    Cursor / Claude Desktop   │
└──────────────┬───────────────┘
               │
               │ MCP over stdio
               ▼
┌──────────────────────────────┐
│       FastMCP Server         │
│                              │
│  Browser tools               │
│  File management tools       │
│  Configuration               │
└──────────────┬───────────────┘
               │
       ┌───────┴────────┐
       ▼                ▼
┌──────────────┐  ┌────────────────┐
│ Browser Agent│  │ File Manager   │
│ browser-use  │  │ pathlib/shutil │
│ Playwright   │  │                │
└──────┬───────┘  └───────┬────────┘
       │                  │
       ▼                  ▼
┌──────────────┐  ┌────────────────┐
│ Websites     │  │ Local Workspace│
│ and Web Data │  │ Downloads/JSON │
└──────────────┘  └────────────────┘
```

## Technology Stack

| Technology | Purpose |
|---|---|
| Python 3.11+ | Main programming language |
| FastMCP | MCP server and tool registration |
| browser-use | AI-driven browser automation |
| Playwright | Browser control and interaction |
| LangChain | LLM integration |
| OpenAI API | Language model for the browser agent |
| pathlib and shutil | Local file management |
| pytest | Automated testing |

## Project Structure

```text
mcp-browser-agent/
├── src/
│   └── mcp_browser_agent/
│       ├── __init__.py
│       ├── server.py
│       ├── browser.py
│       ├── file_manager.py
│       └── config.py
├── tests/
│   ├── test_file_manager.py
│   └── test_server.py
├── workspace/
│   ├── downloads/
│   └── results/
├── .env.example
├── .gitignore
├── requirements.txt
├── pyproject.toml
└── README.md
```

*This is the planned project structure; adjust it to match the files currently implemented in the repository.*

## Prerequisites

Before getting started, install:

- Python 3.11 or newer
- Git
- A supported browser, such as Chromium
- An OpenAI API key if using the OpenAI integration
- An MCP-compatible client, such as Cursor or Claude Desktop

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/mcp-browser-agent.git
cd mcp-browser-agent
```

Replace `YOUR_USERNAME` with your GitHub username.

### 2. Create a virtual environment

**Windows PowerShell**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Linux / macOS**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium
```

If you are installing dependencies manually during initial development, use:

```bash
pip install fastmcp browser-use langchain-openai python-dotenv
```

Ensure the installed package versions are compatible with one another and record a reproducible dependency set before releasing the project.

### 4. Configure environment variables

Create a `.env` file in the project root using `.env.example` as a template.

Example:

```dotenv
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o
WORKSPACE_DIR=./workspace
```

Replace the example API key with your own key.

**Security:** Never commit `.env` or expose API keys in screenshots, logs, source code, or public repositories.

## Running the MCP Server

Once the implementation is complete, start the server from the project root.

For a source layout that supports running the package as a module:

```bash
python -m mcp_browser_agent.server
```

If you are using a standalone `server.py` during early development, run that file using its actual path instead.

The server should use standard input/output (stdio) for MCP communication. Keep diagnostic logging on standard error so it does not interfere with protocol messages.

## Connecting to an MCP Client

### Example configuration

Add the following server entry to your MCP client's configuration, adapting the paths and configuration format to that client's requirements.

```json
{
  "mcpServers": {
    "mcp-browser-agent": {
      "command": "/absolute/path/to/mcp-browser-agent/.venv/bin/python",
      "args": [
        "-m",
        "mcp_browser_agent.server"
      ],
      "env": {
        "OPENAI_API_KEY": "your_openai_api_key",
        "WORKSPACE_DIR": "/absolute/path/to/mcp-browser-agent/workspace"
      }
    }
  }
}
```

**Windows note:** Replace the Python executable with the absolute path to `.venv\\Scripts\\python.exe`. Update the module import path and working-directory configuration to match your implementation.

After saving the configuration, restart or reload the MCP client and verify that the server's tools appear in its tool list.

## Available Tools

The following tools describe the intended functionality. Their actual names and arguments depend on the implementation.

### `automate_web_task`

Runs a browser automation task using the configured AI model.

**Example task:**

> Visit a public website, collect its page title and five relevant links, and return the results as structured data.

Expected workflow:

1. Receive the task from the MCP client.
2. Launch or control the browser.
3. Navigate and interact with the website.
4. Extract the requested information.
5. Save the result when requested.
6. Return a summary to the MCP client.

### `organize_downloaded_files`

Organizes files inside the configured workspace into a designated category directory.

Expected workflow:

1. Validate the source directory.
2. Identify eligible files.
3. Create the destination directory.
4. Move files without unintentionally overwriting existing files.
5. Return a summary of the operation.

> These tools should be considered planned until they have been implemented and tested in the repository.

## Example Workflow

A typical automation workflow looks like this:

```text
User gives a task
        |
        v
MCP client selects a tool
        |
        v
FastMCP receives the request
        |
        v
Browser agent performs the task
        |
        v
Data or files are saved locally
        |
        v
MCP server returns the result
```

Example request to an MCP-enabled assistant:

> Use the browser automation tool to visit a public webpage, extract its title and top five links, and save the results as JSON in the workspace.

Expected output structure:

```json
{
  "url": "https://example.com",
  "title": "Example Domain",
  "links": [
    {
      "text": "More information",
      "url": "https://www.iana.org/help/example-domains"
    }
  ]
}
```

This is an illustrative output format, not a guarantee that every website or browser task will return these exact results.

## Testing

Run the automated test suite from the project root:

```bash
pytest -v
```

Recommended tests include:

- MCP server startup and tool discovery
- Tool input validation
- Successful extraction from a predictable test page
- Browser timeouts and navigation failures
- Download directory creation
- Duplicate filename handling
- Invalid paths and workspace boundary enforcement
- File organization and error reporting

Browser integration tests may require an installed browser and valid model credentials.

## Security Considerations

Autonomous browser agents can interact with websites and access local files, so security must be considered from the beginning.

- Restrict filesystem access to the configured workspace.
- Validate user-provided URLs and prevent access to local or private network services unless explicitly authorized.
- Treat webpage content as untrusted data.
- Never expose API keys or other secrets to website content.
- Require confirmation before consequential actions, including submitting forms, uploading files, or making purchases.
- Avoid overwriting existing files without explicit permission.
- Use appropriate timeouts and limits on browser actions, file sizes, and execution duration.
- Do not use the agent to bypass authentication, access controls, or website restrictions.

## Roadmap

- [ ] Implement the basic FastMCP server.
- [ ] Add configuration management and environment variable validation.
- [ ] Integrate browser-use and Playwright.
- [ ] Implement structured web data extraction.
- [ ] Add reliable file download handling.
- [ ] Implement safe file organization.
- [ ] Add automated tests and error handling.
- [ ] Test integration with Cursor or Claude Desktop.
- [ ] Add usage examples, screenshots, and a demonstration.
- [ ] Publish a complete setup guide.

## Troubleshooting

### MCP server does not start

- Confirm that the configured Python executable exists.
- Activate the correct virtual environment.
- Verify that all required dependencies are installed.
- Run the server manually and inspect error output.

### Browser fails to launch

```bash
playwright install chromium
```

Check that the browser dependencies are available for your operating system.

### API authentication fails

- Confirm that the API key is valid.
- Verify that the environment variable is passed to the server process.
- Check model availability and API account limits.

### MCP tools do not appear

- Verify the client's configuration syntax.
- Check the executable and module paths.
- Restart or reload the MCP client.
- Ensure that the server uses the expected MCP transport.

## Contributing

Contributions, bug reports, and feature suggestions are welcome.

1. Fork the repository.
2. Create a feature branch.
3. Implement and test your changes.
4. Submit a pull request describing the changes.

## License

Choose a license before publishing the project publicly. For example, the MIT License is suitable for many open-source projects; add a `LICENSE` file if you choose it.

## Author

**Your Name**

- GitHub: [polor8689-netizen](https://github.com/polor8689-netizen)

---

Built with Python, FastMCP, browser-use, and Playwright.
