import asyncio
import hashlib
import json
import logging
import os
import re
import sqlite3
import ssl
import urllib.parse
import uuid
from dotenv import load_dotenv

# Load configuration from .env file if present
load_dotenv()

# ==============================================================================
# ENVIRONMENT & CONFIGURATION
# ==============================================================================
CONFIG = {
    "SERVER_NAME": os.getenv("SERVER_NAME", "Siphonix-Server/3.0"),
    "HOST": os.getenv("HOST", "0.0.0.0"),
    "SIP_PORT_UDP": int(os.getenv("SIP_PORT_UDP", 5070)),
    "SIP_PORT_TLS": int(os.getenv("SIP_PORT_TLS", 5071)),
    "WEB_ADMIN_PORT": int(os.getenv("WEB_ADMIN_PORT", 8080)),
    "ADMIN_CREDENTIALS": (
        os.getenv("ADMIN_USERNAME", "admin"),
        os.getenv("ADMIN_PASSWORD", "admin")
    ),
    "REALM": os.getenv("REALM", "siphonix.net"),
    "DB_FILE": os.getenv("DB_FILE", "siphonix.db"),
    "CERT_FILE": os.getenv("CERT_FILE", "server.crt"),
    "KEY_FILE": os.getenv("KEY_FILE", "server.key"),
    "RTP_PORT_RANGE": (
        int(os.getenv("RTP_START_PORT", 10000)),
        int(os.getenv("RTP_END_PORT", 20000))
    ),
    "ENABLE_TLS": os.getenv("ENABLE_TLS", "false").lower() in ("true", "1", "yes")
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
)
logger = logging.getLogger("Siphonix")


# ==============================================================================
# DATABASE PERSISTENCE LAYER
# ==============================================================================
class DatabaseManager:

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    password TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS location (
                    username TEXT PRIMARY KEY,
                    ip TEXT NOT NULL,
                    port INTEGER NOT NULL,
                    contact TEXT NOT NULL,
                    expires INTEGER NOT NULL
                )
            """)
            conn.commit()

    def get_users(self) -> list:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT username, password FROM users")
            return [{"username": r[0], "password": r[1]} for r in cursor.fetchall()]

    def add_user(self, username: str, password: str) -> bool:
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False

    def delete_user(self, username: str):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE username = ?", (username,))
            cursor.execute("DELETE FROM location WHERE username = ?", (username,))
            conn.commit()

    def get_user_password(self, username: str) -> str:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
            row = cursor.fetchone()
            return row[0] if row else None

    def save_location(self, username: str, ip: str, port: int, contact: str, expires: int):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO location (username, ip, port, contact, expires)
                VALUES (?, ?, ?, ?, ?)
            """, (username, ip, port, contact, expires))
            conn.commit()

    def delete_location(self, username: str):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM location WHERE username = ?", (username,))
            conn.commit()

    def get_locations(self) -> list:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT username, ip, port, contact, expires FROM location")
            return [{"username": r[0], "ip": r[1], "port": r[2], "contact": r[3], "expires": r[4]} for r in cursor.fetchall()]

    def get_location(self, username: str):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ip, port, contact FROM location WHERE username = ?", (username,))
            row = cursor.fetchone()
            return {"ip": row[0], "port": row[1], "contact": row[2]} if row else None


# ==============================================================================
# ADMINISTRATIVE WEB DASHBOARD
# ==============================================================================
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Siphonix Console</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #121214; color: #e1e1e6; margin: 0; padding: 20px; }
        h1, h2 { color: #00d26a; }
        .container { max-width: 1000px; margin: 0 auto; }
        .card { background: #202024; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { padding: 10px; text-align: left; border-bottom: 1px solid #323238; }
        th { background: #29292e; color: #00d26a; }
        input, button { padding: 10px; border-radius: 4px; border: 1px solid #323238; background: #121214; color: #fff; margin-right: 5px; }
        button { background: #00d26a; color: #000; font-weight: bold; cursor: pointer; border: none; }
        button.danger { background: #f85149; color: #fff; }
        .badge { background: #00d26a22; color: #00d26a; padding: 4px 8px; border-radius: 4px; font-size: 12px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Siphonix — Administration Console</h1>
        
        <div class="card">
            <h2>Provision SIP User</h2>
            <form method="POST" action="/api/users/add">
                <input type="text" name="username" placeholder="Username" required>
                <input type="password" name="password" placeholder="Password" required>
                <button type="submit">Create User</button>
            </form>
        </div>

        <div class="card">
            <h2>Registered Users</h2>
            <table>
                <tr><th>Username</th><th>Password</th><th>Action</th></tr>
                {USERS_ROWS}
            </table>
        </div>

        <div class="card">
            <h2>Active SIP Registrations</h2>
            <table>
                <tr><th>Username</th><th>Network Endpoint</th><th>Contact Header</th><th>Expires</th></tr>
                {LOCATIONS_ROWS}
            </table>
        </div>
    </div>
</body>
</html>
"""

class WebAdminServer:

    def __init__(self, db: DatabaseManager):
        self.db = db

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        data = await reader.read(4096)
        request = data.decode("utf-8", errors="ignore")
        if not request:
            writer.close()
            return

        lines = request.split("\r\n")
        first_line = lines[0].split(" ")
        if len(first_line) < 2:
            writer.close()
            return

        method, path = first_line[0], first_line[1]

        # Process API User Creation
        if method == "POST" and path == "/api/users/add":
            body = request.split("\r\n\r\n")[1] if "\r\n\r\n" in request else ""
            params = urllib.parse.parse_qs(body)
            username = params.get("username", [""])[0]
            password = params.get("password", [""])[0]
            if username and password:
                self.db.add_user(username, password)
            writer.write(b"HTTP/1.1 302 Found\r\nLocation: /\r\n\r\n")
            await writer.drain()
            writer.close()
            return

        # Process API User Deletion
        if method == "GET" and path.startswith("/api/users/delete"):
            query = urllib.parse.urlparse(path).query
            params = urllib.parse.parse_qs(query)
            username = params.get("username", [""])[0]
            if username:
                self.db.delete_user(username)
            writer.write(b"HTTP/1.1 302 Found\r\nLocation: /\r\n\r\n")
            await writer.drain()
            writer.close()
            return

        # Render Dashboard View
        users = self.db.get_users()
        locations = self.db.get_locations()

        users_rows = "".join([
            f"<tr><td><b>{u['username']}</b></td><td><code>{u['password']}</code></td>"
            f"<td><a href='/api/users/delete?username={u['username']}'><button class='danger'>Delete</button></a></td></tr>"
            for u in users
        ])

        locations_rows = "".join([
            f"<tr><td><span class='badge'>{l['username']}</span></td><td>{l['ip']}:{l['port']}</td>"
            f"<td><code>{l['contact']}</code></td><td>{l['expires']}s</td></tr>"
            for l in locations
        ]) or "<tr><td colspan='4'>No active SIP registrations.</td></tr>"

        html = HTML_TEMPLATE.replace("{USERS_ROWS}", users_rows).replace("{LOCATIONS_ROWS}", locations_rows)

        response = f"HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: {len(html.encode())}\r\n\r\n{html}"
        writer.write(response.encode("utf-8"))
        await writer.drain()
        writer.close()


# ==============================================================================
# CORE SIP ENGINE
# ==============================================================================
class SIPParser:

    @staticmethod
    def parse(data: str) -> dict:
        lines = data.split("\r\n")
        if not lines or not lines[0]:
            return None

        msg = {"headers": {}, "body": ""}
        first_line = lines[0].strip().split(" ")

        if len(first_line) < 3:
            return None

        if first_line[0].startswith("SIP/2.0"):
            msg["type"] = "RESPONSE"
            msg["version"] = first_line[0]
            msg["status_code"] = int(first_line[1])
            msg["reason"] = " ".join(first_line[2:])
        else:
            msg["type"] = "REQUEST"
            msg["method"] = first_line[0]
            msg["uri"] = first_line[1]
            msg["version"] = first_line[2]

        i = 1
        while i < len(lines) and lines[i] != "":
            header_line = lines[i]
            if ":" in header_line:
                key, val = header_line.split(":", 1)
                msg["headers"][key.strip().lower()] = val.strip()
            i += 1

        if i + 1 < len(lines):
            msg["body"] = "\r\n".join(lines[i + 1:])

        return msg

    @staticmethod
    def extract_uri_user(uri: str) -> str:
        match = re.search(r"sip:([^@>]+)@", uri)
        if match:
            return match.group(1)
        match_simple = re.search(r"sip:([^@>;]+)", uri)
        return match_simple.group(1) if match_simple else uri


class SIPAuth:

    def __init__(self, realm: str, db: DatabaseManager):
        self.realm = realm
        self.db = db

    def verify_auth(self, method: str, auth_header: str) -> bool:
        if not auth_header or not auth_header.startswith("Digest "):
            return False

        content = auth_header[7:]
        params = {}
        for key, val1, val2 in re.findall(r'(\w+)=(?:"([^"]+)"|([^\s,]+))', content):
            params[key] = val1 if val1 else val2

        username = params.get("username")
        password = self.db.get_user_password(username)
        if not password:
            return False

        ha1 = hashlib.md5(f"{username}:{self.realm}:{password}".encode()).hexdigest()
        ha2 = hashlib.md5(f"{method}:{params.get('uri')}".encode()).hexdigest()
        expected = hashlib.md5(f"{ha1}:{params.get('nonce')}:{ha2}".encode()).hexdigest()

        return params.get("response") == expected


class SIPCoreProtocol(asyncio.DatagramProtocol):

    def __init__(self, db: DatabaseManager):
        self.db = db
        self.auth = SIPAuth(CONFIG["REALM"], db)
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport
        logger.info(f"SIP engine initialized on UDP endpoint {CONFIG['HOST']}:{CONFIG['SIP_PORT_UDP']}")

    def datagram_received(self, data: bytes, addr: tuple):
        try:
            raw_msg = data.decode("utf-8", errors="ignore")
            msg = SIPParser.parse(raw_msg)
            if not msg:
                return

            if msg["type"] == "REQUEST":
                self.handle_request(msg, addr, raw_msg)
            elif msg["type"] == "RESPONSE":
                self.handle_response(msg, addr, raw_msg)

        except Exception as e:
            logger.error(f"Failed to process packet from {addr}: {e}", exc_info=True)

    def send_response(self, addr: tuple, code: int, reason: str, request_msg: dict, extra_headers: dict = None):
        headers = request_msg["headers"]
        response_lines = [f"SIP/2.0 {code} {reason}"]

        for h in ["via", "from", "to", "call-id", "cseq"]:
            if h in headers:
                hdr_name = "-".join([w.capitalize() for w in h.split("-")])
                val = headers[h]
                if h == "to" and "tag=" not in val.lower() and code >= 200:
                    val += f";tag={uuid.uuid4().hex[:8]}"
                response_lines.append(f"{hdr_name}: {val}")

        response_lines.append(f"Server: {CONFIG['SERVER_NAME']}")

        if extra_headers:
            for k, v in extra_headers.items():
                response_lines.append(f"{k}: {v}")

        response_lines.append("Content-Length: 0")
        response_lines.append("\r\n")

        self.transport.sendto("\r\n".join(response_lines).encode("utf-8"), addr)

    def handle_request(self, msg: dict, addr: tuple, raw_msg: str):
        method = msg["method"]
        user_from = SIPParser.extract_uri_user(msg["headers"].get("from", ""))
        user_to = SIPParser.extract_uri_user(msg["headers"].get("to", ""))

        if method == "REGISTER":
            self.process_register(msg, addr, user_from)
        elif method in ["INVITE", "ACK", "BYE", "CANCEL", "OPTIONS"]:
            if method == "OPTIONS":
                self.send_response(addr, 200, "OK", msg)
                return
            
            target = self.db.get_location(user_to)
            if target:
                if method == "INVITE":
                    self.send_response(addr, 100, "Trying", msg)
                self.transport.sendto(raw_msg.encode("utf-8"), (target["ip"], target["port"]))
            else:
                self.send_response(addr, 404, "Not Found", msg)

    def process_register(self, msg: dict, addr: tuple, username: str):
        auth_hdr = msg["headers"].get("authorization")

        if not auth_hdr or not self.auth.verify_auth("REGISTER", auth_hdr):
            nonce = hashlib.md5(os.urandom(16)).hexdigest()
            challenge = f'Digest realm="{CONFIG["REALM"]}", nonce="{nonce}", algorithm=MD5'
            self.send_response(addr, 401, "Unauthorized", msg, {"WWW-Authenticate": challenge})
            return

        expires = int(msg["headers"].get("expires", 3600))
        contact = msg["headers"].get("contact", "")

        if expires == 0 or not contact:
            self.db.delete_location(username)
            self.send_response(addr, 200, "OK", msg)
        else:
            self.db.save_location(username, addr[0], addr[1], contact, expires)
            self.send_response(addr, 200, "OK", msg, {"Contact": contact, "Expires": str(expires)})

    def handle_response(self, msg: dict, addr: tuple, raw_msg: str):
        user_from = SIPParser.extract_uri_user(msg["headers"].get("from", ""))
        sender = self.db.get_location(user_from)
        if sender:
            self.transport.sendto(raw_msg.encode("utf-8"), (sender["ip"], sender["port"]))


# ==============================================================================
# APPLICATION BOOTSTRAP
# ==============================================================================
async def main():
    db = DatabaseManager(CONFIG["DB_FILE"])
    web_admin = WebAdminServer(db)
    loop = asyncio.get_running_loop()

    # 1. Initialize UDP SIP Protocol Endpoint
    udp_transport, sip_protocol = await loop.create_datagram_endpoint(
        lambda: SIPCoreProtocol(db),
        local_addr=(CONFIG["HOST"], CONFIG["SIP_PORT_UDP"])
    )

    # 2. Launch Administrative Web Server
    admin_server = await asyncio.start_server(
        web_admin.handle_client,
        host=CONFIG["HOST"],
        port=CONFIG["WEB_ADMIN_PORT"]
    )

    logger.info(f"Administrative Web Console accessible at http://localhost:{CONFIG['WEB_ADMIN_PORT']}")

    async with admin_server:
        await asyncio.gather(
            admin_server.serve_forever(),
            asyncio.sleep(3600 * 24 * 365)
        )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutdown signal received. Terminating Siphonix server processes.")