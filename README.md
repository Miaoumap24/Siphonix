## Quick Start Guide

### 1. Repository Setup & Environment Isolation

Clone the project repository and navigate to the project root directory:

```bash
git clone https://github.com/Miaoumap24/siphonix.git
cd siphonix

```

Create and activate a Python virtual environment:

```bash
# On Linux / macOS
python3 -m venv venv
source venv/bin/activate

# On Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1

```

### 2. Dependency Installation

Install the required Python packages using `pip`:

```bash
pip install -r requirements.txt

```

### 3. Environment Configuration

Copy the sample environment file to create your active `.env` configuration file:

```bash
cp .env.example .env

```

Review and adjust variables in `.env` as needed:

```env
SERVER_NAME=Siphonix-Server/3.0
HOST=0.0.0.0
REALM=localhost
SIP_PORT_UDP=5070
WEB_ADMIN_PORT=8080
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin
DB_FILE=siphonix.db

```

### 4. Running the Server

Start the application:

```bash
python app.py

```

Upon successful startup, the server outputs confirmation logs:

```text
2026-09-04 19:22:00,000 [INFO] [Siphonix] SIP engine initialized on UDP endpoint 0.0.0.0:5070
2026-09-04 19:22:00,001 [INFO] [Siphonix] Administrative Web Console accessible at http://localhost:8080

```

---

## Configuration Reference (`.env.example`)

Below is the complete reference table for all supported environment variables:

| Variable | Type | Default Value | Description |
| --- | --- | --- | --- |
| `SERVER_NAME` | String | `Siphonix-Server/3.0` | Value exposed in the `Server:` SIP header. |
| `HOST` | IP Address | `0.0.0.0` | Bind interface address for SIP and Web Admin servers. |
| `REALM` | String | `siphonix.net` | Security domain used for SIP Digest Authentication hashing. |
| `SIP_PORT_UDP` | Integer | `5070` | Local UDP listening port for incoming SIP traffic. |
| `SIP_PORT_TLS` | Integer | `5071` | Reserved TLS port for encrypted SIP transport. |
| `ENABLE_TLS` | Boolean | `false` | Enables/disables TLS socket binding. |
| `WEB_ADMIN_PORT` | Integer | `8080` | Local TCP listening port for the Web Console. |
| `ADMIN_USERNAME` | String | `admin` | Username for basic HTTP authorization access. |
| `ADMIN_PASSWORD` | String | `admin` | Password for basic HTTP authorization access. |
| `DB_FILE` | Path | `siphonix.db` | File path for SQLite database storage. |
| `CERT_FILE` | Path | `server.crt` | Path to TLS public certificate file. |
| `KEY_FILE` | Path | `server.key` | Path to TLS private key file. |
| `RTP_START_PORT` | Integer | `10000` | Start of the RTP audio/video port range allocation. |
| `RTP_END_PORT` | Integer | `20000` | End of the RTP audio/video port range allocation. |

---

## Architectural Workflow

```text
                      +-----------------------------+
                      |   SIP Softphone / Client    |
                      +--------------+--------------+
                                     |
                                     | 1. REGISTER (No Auth)
                                     v
+------------------------------------+------------------------------------+
|  Siphonix Core Server                                                   |
|                                                                         |
|   +-------------------+    401 Unauthorized    +--------------------+   |
|   | SIP Core Protocol | ---------------------> | SIP Client         |   |
|   | Engine (UDP)      | <--------------------- | (With MD5 Response)|   |
|   +---------+---------+   2. REGISTER + Auth   +--------------------+   |
|             |                                                           |
|             | 3. Digest Validation                                      |
|             v                                                           |
|   +-------------------+                        +--------------------+   |
|   | SQLite DB Manager | <--------------------->| Location Registry  |   |
|   +---------+---------+                        +--------------------+   |
|             |                                                           |
|             | 4. Sync State                                             |
|             v                                                           |
|   +-------------------+                        +--------------------+   |
|   | Web Admin Console | ---------------------> | Administrator Browser |
|   | Server (HTTP)     |    Render Dashboard    | (Port 8080)        |   |
|   +-------------------+                        +--------------------+   |
+-------------------------------------------------------------------------+

```

---

## Administrative Console Usage

Access the web dashboard by navigating to `http://localhost:8080` in your web browser.

### Key Features

1. **User Provisioning**: Fill in the **Provision SIP User** form with a username and password, then click **Create User**.
2. **Account Directory**: View all configured accounts under **Registered Users** and remove accounts using the **Delete** button.
3. **Session Monitor**: Track live endpoint registrations, socket addresses (`IP:Port`), Contact URIs, and remaining expiry timers in real time.

---

## Connecting SIP Softphones

To connect softphones like **Linphone**, **MicroSIP**, or **Zoiper**:

1. **Username**: Set to the username created via the Web Admin Console (e.g., `1001`).
2. **Password**: Set to the user's password.
3. **Domain / Realm / Registrar**: Enter your server address and port (e.g., `127.0.0.1:5070` or `localhost`).
4. **Transport**: Select **UDP**.

---

## License

This project is licensed under the AGPL-3.0 License — see the LICENSE file for details.
