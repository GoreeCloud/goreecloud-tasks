#!/usr/bin/env python3
"""Render real GoreeCloud Tasks templates and validate the Glaze UI adoption in Chromium."""

from __future__ import annotations

import contextlib
import functools
import http.server
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RENDER_ATTEMPTS = 2
RENDER_TIMEOUT_SECONDS = 45

SNAPSHOTS = (
    ("dashboard", "/"),
    ("task-detail", "task-detail"),
    ("notifications", "notifications"),
    ("data", "data"),
    ("login", "login"),
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"Tasks Glaze rendered acceptance failed: {message}")


def find_browser() -> str:
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        path = shutil.which(name)
        if path:
            return path
    raise SystemExit("Tasks Glaze rendered acceptance failed: no supported Chromium-family browser found")


def build_snapshots(root: Path) -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "goreecloud_tasks.settings")
    os.environ.setdefault("DJANGO_SECRET_KEY", "glaze-rendered-acceptance-only-secret")
    os.environ.setdefault("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
    os.environ.setdefault("DATABASE_ENGINE", "sqlite")

    import django

    django.setup()

    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.core.management import call_command
    from django.db import connections
    from django.test import Client
    from django.urls import reverse

    from tasks.models import Task

    database_path = root / "acceptance.sqlite3"
    settings.DATABASES["default"]["NAME"] = database_path
    connections.databases["default"]["NAME"] = database_path
    connections.close_all()

    call_command("migrate", verbosity=0, interactive=False)

    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="glaze-acceptance",
        password="glaze-acceptance-only-password",
        display_name="Glaze Acceptance",
    )
    task = Task.objects.create(
        title="Review Glaze UI consumer acceptance",
        description="Representative task used only by the rendered CI fixture.",
        creator=user,
        assignee=user,
        priority=Task.Priority.P2_HIGH,
        status=Task.Status.IN_PROGRESS,
        is_goreecloud_work=True,
        assigned_service="GoreeCloud Tasks",
        validation_requirement=True,
        documentation_requirement=True,
    )

    authenticated = Client()
    authenticated.force_login(user)
    anonymous = Client()

    routes = {
        "dashboard": reverse("tasks:dashboard"),
        "task-detail": reverse("tasks:task_detail", args=[task.pk]),
        "notifications": reverse("notifications:settings"),
        "data": reverse("portability:index"),
        "login": reverse("login"),
    }

    for name, _placeholder in SNAPSHOTS:
        client = anonymous if name == "login" else authenticated
        response = client.get(routes[name], HTTP_HOST="testserver")
        require(response.status_code == 200, f"{name} fixture returned HTTP {response.status_code}")
        html = response.content.decode("utf-8")
        require('data-glaze-ui="1.3.0"' in html, f"{name} fixture lost Glaze version marker")
        require("css/glaze.css" in html, f"{name} fixture did not load glaze.css")
        (root / f"{name}.html").write_text(html, encoding="utf-8")

    shutil.copytree(ROOT / "static", root / "static", dirs_exist_ok=True)
    (root / "acceptance.html").write_text(acceptance_page(), encoding="utf-8")
    connections.close_all()


def acceptance_page() -> str:
    snapshot_names = ",".join(f'"{name}"' for name, _ in SNAPSHOTS)
    return f"""<!doctype html>
<html lang=\"en\" data-status=\"pending\">
<head>
<meta charset=\"utf-8\">
<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<title>Tasks Glaze UI rendered acceptance</title>
<style>
html,body{{margin:0;padding:0;background:#fff;color:#000;font:14px system-ui,sans-serif}}
iframe{{display:block;width:100vw;height:1000px;border:0}}
#result{{position:fixed;inset:auto 0 0 0;z-index:9999;margin:0;padding:8px;background:#fff;color:#000;white-space:pre-wrap}}
</style>
</head>
<body>
<div id=\"frames\"></div><pre id=\"result\">PENDING</pre>
<script>
const pages=[{snapshot_names}];
const params=new URLSearchParams(location.search);
const expectedTheme=params.get('theme')||'light';
const mode=params.get('mode')||'normal';
const failures=[];
const note=(ok,message)=>{{if(!ok) failures.push(message)}};
const durationMs=(value)=>Math.max(...value.split(',').map(part=>{{
  const item=part.trim();
  if(item.endsWith('ms')) return parseFloat(item)||0;
  if(item.endsWith('s')) return (parseFloat(item)||0)*1000;
  return 0;
}}));

function visible(element){{
  const style=getComputedStyle(element);
  const rect=element.getBoundingClientRect();
  return style.display!=='none'&&style.visibility!=='hidden'&&rect.width>0&&rect.height>0;
}}

function inspect(frame,name){{
  const doc=frame.contentDocument;
  const win=frame.contentWindow;
  note(Boolean(doc),`${{name}} has no contentDocument`);
  if(!doc) return;
  const root=doc.documentElement;
  note(root.dataset.glazeUi==='1.3.0',`${{name}} lost data-glaze-ui=1.3.0`);
  note(root.dataset.glazeConsumerStatus==='adoption-candidate',`${{name}} lost Adoption Candidate marker`);
  const sheets=[...doc.querySelectorAll('link[rel=stylesheet]')].map(link=>link.getAttribute('href')||'');
  note(sheets.length>0 && sheets[sheets.length-1].includes('css/glaze.css'),`${{name}} does not load glaze.css last`);

  const rootStyle=win.getComputedStyle(root);
  const expectedCanvas=expectedTheme==='dark'?'#0d1119':'#eef3f9';
  note(rootStyle.getPropertyValue('--glaze-canvas').trim().toLowerCase()===expectedCanvas,`${{name}} did not activate ${{expectedTheme}} Glaze tokens`);
  note(rootStyle.getPropertyValue('--glaze-target-min').trim()==='44px',`${{name}} lost 44px target token`);

  note(doc.documentElement.scrollWidth<=frame.clientWidth+1,`${{name}} horizontally overflows ${{frame.clientWidth}}px viewport: ${{doc.documentElement.scrollWidth}}px`);

  const controls=[...doc.querySelectorAll('button,input:not([type=checkbox]):not([type=radio]):not([type=hidden]),select,textarea,a.nav-item,a.secondary-link,a.button')].filter(visible);
  note(controls.length>0,`${{name}} exposes no representative interactive controls`);
  for(const control of controls){{
    const rect=control.getBoundingClientRect();
    if(control.matches('textarea')) continue;
    note(rect.height>=43.5,`${{name}} control below 44px: ${{control.tagName}}.${{control.className}} = ${{rect.height.toFixed(1)}}px`);
  }}

  const completion=doc.querySelector('.complete-button');
  if(completion && visible(completion)){{
    const rect=completion.getBoundingClientRect();
    note(rect.width>=43.5&&rect.height>=43.5,`${{name}} completion target is ${{rect.width.toFixed(1)}}x${{rect.height.toFixed(1)}}`);
  }}

  const nav=doc.querySelector('.nav-item');
  if(nav && visible(nav)) note(nav.getBoundingClientRect().height>=43.5,`${{name}} navigation target is below 44px`);

  if(mode==='reduced-motion'){{
    const motionTarget=controls[0]||doc.body;
    note(durationMs(win.getComputedStyle(motionTarget).transitionDuration)<=0.1,`${{name}} reduced-motion transition remains active`);
  }}
}}

async function run(){{
  note(matchMedia(`(prefers-color-scheme: ${{expectedTheme}})`).matches,`browser did not enter expected ${{expectedTheme}} color scheme`);
  if(mode==='reduced-motion') note(matchMedia('(prefers-reduced-motion: reduce)').matches,'browser did not activate reduced motion');
  if(mode==='forced-colors') note(matchMedia('(forced-colors: active)').matches,'browser did not activate forced colors');

  const host=document.getElementById('frames');
  const frames=pages.map(name=>{{
    const frame=document.createElement('iframe');
    frame.dataset.page=name;
    frame.src=`/${{name}}.html`;
    host.appendChild(frame);
    return frame;
  }});
  await Promise.all(frames.map(frame=>new Promise(resolve=>{{frame.addEventListener('load',resolve,{{once:true}});}})));
  await new Promise(resolve=>setTimeout(resolve,150));
  for(const frame of frames) inspect(frame,frame.dataset.page);

  const result=document.getElementById('result');
  if(failures.length){{
    document.documentElement.dataset.status='fail';
    result.textContent='FAIL\\n'+failures.join('\\n');
  }}else{{
    document.documentElement.dataset.status='pass';
    result.textContent='PASS';
  }}
}}
run();
</script>
</body></html>"""


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


@contextlib.contextmanager
def serve(root: Path):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    handler = functools.partial(QuietHandler, directory=str(root))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield port
    finally:
        server.shutdown()
        thread.join(timeout=5)


def browser_command(browser: str, url: str, profile: str, *, width: int, height: int, theme: str, mode: str) -> list[str]:
    command = [
        browser,
        "--headless=new",
        "--no-sandbox",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--disable-background-networking",
        "--disable-default-apps",
        "--disable-extensions",
        "--disable-sync",
        "--no-first-run",
        "--mute-audio",
        "--run-all-compositor-stages-before-draw",
        "--virtual-time-budget=6500",
        f"--user-data-dir={profile}",
        f"--window-size={width},{height}",
    ]
    if theme == "dark":
        command.append("--force-dark-mode")
    if mode == "reduced-motion":
        command.append("--force-prefers-reduced-motion")
    elif mode == "forced-colors":
        command.append("--force-high-contrast")
    command.extend(["--dump-dom", url])
    return command


def run_case(browser: str, port: int, *, width: int, height: int, theme: str, mode: str = "normal") -> None:
    url = f"http://127.0.0.1:{port}/acceptance.html?theme={theme}&mode={mode}"
    case = f"{width}x{height} {theme} {mode}"
    last = "no browser result"
    for attempt in range(1, RENDER_ATTEMPTS + 1):
        with tempfile.TemporaryDirectory(prefix="tasks-glaze-profile-") as profile:
            try:
                result = subprocess.run(
                    browser_command(browser, url, profile, width=width, height=height, theme=theme, mode=mode),
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    timeout=RENDER_TIMEOUT_SECONDS,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                output = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
                last = f"attempt {attempt} timed out\n{output[-3000:]}"
                if attempt < RENDER_ATTEMPTS:
                    continue
                break
        if result.returncode == 0 and 'data-status="pass"' in result.stdout and "PASS" in result.stdout:
            print(f"Tasks Glaze rendered acceptance passed: {case}")
            return
        last = (result.stdout or result.stderr)[-5000:]
        if attempt < RENDER_ATTEMPTS:
            print(f"Tasks Glaze rendered acceptance retrying: {case}")
    raise SystemExit(f"Tasks Glaze rendered acceptance failed for {case}:\n{last}")


def main() -> None:
    browser = find_browser()
    with tempfile.TemporaryDirectory(prefix="tasks-glaze-render-") as directory:
        root = Path(directory)
        build_snapshots(root)
        with serve(root) as port:
            for width, height in ((390, 844), (1280, 900)):
                for theme in ("light", "dark"):
                    run_case(browser, port, width=width, height=height, theme=theme)
            run_case(browser, port, width=390, height=844, theme="light", mode="reduced-motion")
            run_case(browser, port, width=390, height=844, theme="light", mode="forced-colors")
    print("GoreeCloud Tasks representative Glaze UI rendered acceptance passed")


if __name__ == "__main__":
    main()
