#!/usr/bin/env python3
"""Render real GoreeCloud Tasks templates and validate the GLAZE UI V1.0 migration in Chromium."""

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

TARGET_VERSION = "1.0.0"
GLAZE_SOURCE_REVISION = "70909bbdccad378fb7281ae1842e2f5beed64c38"
RENDER_ATTEMPTS = 2
RENDER_TIMEOUT_SECONDS = 45
SNAPSHOTS = ("dashboard", "task-detail", "notifications", "data", "login")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"Tasks GLAZE UI V1.0 rendered acceptance failed: {message}")


def find_browser() -> str:
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        if path := shutil.which(name):
            return path
    raise SystemExit("Tasks GLAZE UI V1.0 rendered acceptance failed: no Chromium-family browser found")


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

    user = get_user_model().objects.create_user(
        username="glaze-acceptance",
        password="glaze-acceptance-only-password",
        display_name="Glaze Acceptance",
    )
    task = Task.objects.create(
        title="Review GLAZE UI V1.0 consumer acceptance",
        description="Representative rendered-acceptance task.",
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

    for name in SNAPSHOTS:
        response = (anonymous if name == "login" else authenticated).get(routes[name], HTTP_HOST="testserver")
        require(response.status_code == 200, f"{name} fixture returned HTTP {response.status_code}")
        html = response.content.decode("utf-8")
        require(f'data-glaze-ui="{TARGET_VERSION}"' in html, f"{name} lost V1 version marker")
        require(
            f'data-glaze-source-revision="{GLAZE_SOURCE_REVISION}"' in html,
            f"{name} lost exact canonical V1 source provenance",
        )
        require(
            'data-glaze-consumer-status="migration-in-progress"' in html,
            f"{name} overclaimed Glaze consumer status",
        )
        require("css/glaze.css" in html, f"{name} did not load glaze.css")
        (root / f"{name}.html").write_text(html, encoding="utf-8")

    shutil.copytree(ROOT / "static", root / "static", dirs_exist_ok=True)
    (root / "acceptance.html").write_text(acceptance_page(), encoding="utf-8")
    connections.close_all()


def acceptance_page() -> str:
    pages = ",".join(f'"{name}"' for name in SNAPSHOTS)
    return f'''<!doctype html>
<html lang="en" data-status="pending">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tasks GLAZE UI V1.0 rendered acceptance</title>
<style>
html,body{{margin:0;padding:0;background:#fff;color:#000;font:14px system-ui,sans-serif}}
iframe{{display:block;width:100vw;height:1000px;border:0}}
#result{{position:fixed;inset:auto 0 0;z-index:9999;margin:0;padding:8px;background:#fff;color:#000;white-space:pre-wrap}}
</style>
</head>
<body>
<div id="frames"></div><pre id="result">PENDING</pre>
<script>
const pages=[{pages}];
const params=new URLSearchParams(location.search);
const expectedTheme=params.get('theme')||'light';
const mode=params.get('mode')||'normal';
const failures=[];
const note=(ok,message)=>{{if(!ok) failures.push(message)}};
const durationMs=value=>Math.max(...value.split(',').map(part=>{{
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

function applyMode(root){{
  if(mode==='touch-assistance'){{
    root.dataset.glzInput='touch';
    root.dataset.glzTouchAssistance='true';
  }} else if(mode==='text-200'){{
    root.dataset.glzTextScale='200';
  }} else if(mode==='reduced-transparency'){{
    root.dataset.glzTransparency='reduced';
  }} else if(mode==='increased-contrast'){{
    root.dataset.mode='increased-contrast';
  }}
}}

function inspect(frame,name){{
  const doc=frame.contentDocument;
  const win=frame.contentWindow;
  note(Boolean(doc),`${name} has no contentDocument`);
  if(!doc) return;

  const root=doc.documentElement;
  applyMode(root);
  const rootStyle=win.getComputedStyle(root);
  note(root.dataset.glazeUi==='1.0.0',`${name} lost data-glaze-ui=1.0.0`);
  note(root.dataset.glazeSourceRevision==='70909bbdccad378fb7281ae1842e2f5beed64c38',`${name} lost exact canonical V1 source provenance`);
  note(root.dataset.glazeConsumerStatus==='migration-in-progress',`${name} overclaimed downstream acceptance`);

  const sheets=[...doc.querySelectorAll('link[rel=stylesheet]')].map(link=>link.getAttribute('href')||'');
  note(sheets.length>0&&sheets[sheets.length-1].includes('css/glaze.css'),`${name} does not load glaze.css last`);
  note(rootStyle.getPropertyValue('--tasks-glaze-version').trim().replaceAll('"','')==='1.0.0',`${name} lost V1 source marker`);
  note(rootStyle.getPropertyValue('--tasks-glaze-source-revision').trim().replaceAll('"','')==='70909bbdccad378fb7281ae1842e2f5beed64c38',`${name} lost source revision token`);
  note(rootStyle.getPropertyValue('--glz1-target-shell').trim()==='48px',`${name} lost 48px V1 target token`);
  note(rootStyle.getPropertyValue('--glz1-target-assisted').trim()==='56px',`${name} lost 56px assisted target token`);

  if(mode==='forced-colors'){{
    note(rootStyle.getPropertyValue('--glz1-canvas').trim().toLowerCase()==='canvas',`${name} did not activate forced-colors Canvas semantics`);
    note(rootStyle.getPropertyValue('--glz1-focus').trim().toLowerCase()==='highlight',`${name} did not activate forced-colors Highlight focus semantics`);
  }} else {{
    const expectedCanvas=expectedTheme==='dark'?'#0b0d11':'#f5f7fa';
    note(rootStyle.getPropertyValue('--glz1-canvas').trim().toLowerCase()===expectedCanvas,`${name} did not activate ${expectedTheme} V1 tokens`);
  }}

  if(mode==='touch-assistance'){{
    note(root.dataset.glzInput==='touch',`${name} did not enter explicit touch input mode`);
    note(root.dataset.glzTouchAssistance==='true',`${name} did not enter Touch Assistance mode`);
  }}
  if(mode==='text-200'){{
    note(root.dataset.glzTextScale==='200',`${name} did not enter explicit 200% text mode`);
    note(parseFloat(rootStyle.fontSize)>=31.5,`${name} 200% text scale did not reach 32px-equivalent root text`);
  }}
  if(mode==='increased-contrast'){{
    note(rootStyle.getPropertyValue('--glz1-focus-width').trim()==='4px',`${name} increased contrast did not strengthen focus geometry`);
  }}

  note(doc.documentElement.scrollWidth<=frame.clientWidth+1,`${name} horizontally overflows ${frame.clientWidth}px viewport: ${doc.documentElement.scrollWidth}px`);

  const controls=[...doc.querySelectorAll('button,input:not([type=checkbox]):not([type=radio]):not([type=hidden]),select,textarea,a.nav-item,a.secondary-link,a.button')].filter(visible);
  note(controls.length>0,`${name} exposes no representative interactive controls`);
  for(const control of controls){{
    const rect=control.getBoundingClientRect();
    if(control.matches('textarea')) continue;
    const minimum=mode==='touch-assistance'?55.5:47.5;
    note(rect.height>=minimum,`${name} control below ${mode==='touch-assistance'?'56':'48'}px: ${control.tagName}.${control.className} = ${rect.height.toFixed(1)}px`);
  }}

  const completion=doc.querySelector('.complete-button');
  if(completion&&visible(completion)){{
    const rect=completion.getBoundingClientRect();
    const minimum=mode==='touch-assistance'?55.5:47.5;
    note(rect.width>=minimum&&rect.height>=minimum,`${name} completion target is ${rect.width.toFixed(1)}x${rect.height.toFixed(1)}`);
  }}

  const nav=doc.querySelector('.nav-item');
  if(nav&&visible(nav)){{
    const minimum=mode==='touch-assistance'?55.5:47.5;
    note(nav.getBoundingClientRect().height>=minimum,`${name} navigation target is below V1 floor`);
  }}

  if(mode==='reduced-motion'){{
    const motionTarget=controls[0]||doc.body;
    note(durationMs(win.getComputedStyle(motionTarget).transitionDuration)<=0.1,`${name} reduced-motion transition remains active`);
  }}
  if(mode==='reduced-transparency'){{
    for(const surface of doc.querySelectorAll('.topbar,.sidebar')){{
      if(!visible(surface)) continue;
      const style=win.getComputedStyle(surface);
      note(style.backdropFilter==='none'||style.webkitBackdropFilter==='none',`${name} reduced transparency left backdrop filtering active`);
    }}
  }}
}}

async function run(){{
  note(matchMedia(`(prefers-color-scheme: ${expectedTheme})`).matches,`browser did not enter expected ${expectedTheme} color scheme`);
  if(mode==='reduced-motion') note(matchMedia('(prefers-reduced-motion: reduce)').matches,'browser did not activate reduced motion');
  if(mode==='forced-colors') note(matchMedia('(forced-colors: active)').matches,'browser did not activate forced colors');

  const host=document.getElementById('frames');
  const frames=pages.map(name=>{{
    const frame=document.createElement('iframe');
    frame.dataset.page=name;
    frame.src=`/${name}.html`;
    host.appendChild(frame);
    return frame;
  }});
  await Promise.all(frames.map(frame=>new Promise(resolve=>frame.addEventListener('load',resolve,{{once:true}}))));
  await new Promise(resolve=>setTimeout(resolve,150));
  for(const frame of frames) inspect(frame,frame.dataset.page);

  const result=document.getElementById('result');
  if(failures.length){{
    document.documentElement.dataset.status='fail';
    result.textContent='FAIL\n'+failures.join('\n');
  }} else {{
    document.documentElement.dataset.status='pass';
    result.textContent='PASS';
  }}
}}
run();
</script>
</body></html>'''


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
    return [*command, "--dump-dom", url]


def run_case(browser: str, port: int, *, width: int, height: int, theme: str, mode: str = "normal") -> None:
    url = f"http://127.0.0.1:{port}/acceptance.html?theme={theme}&mode={mode}"
    case = f"{width}x{height} {theme} {mode}"
    last = "no browser result"
    for attempt in range(1, RENDER_ATTEMPTS + 1):
        with tempfile.TemporaryDirectory(prefix="tasks-glaze-v1-profile-") as profile:
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
            print(f"Tasks GLAZE UI V1.0 rendered acceptance passed: {case}")
            return
        last = (result.stdout or result.stderr)[-5000:]
        if attempt < RENDER_ATTEMPTS:
            print(f"Tasks GLAZE UI V1.0 rendered acceptance retrying: {case}")
    raise SystemExit(f"Tasks GLAZE UI V1.0 rendered acceptance failed for {case}:\n{last}")


def main() -> None:
    browser = find_browser()
    with tempfile.TemporaryDirectory(prefix="tasks-glaze-v1-render-") as directory:
        root = Path(directory)
        build_snapshots(root)
        with serve(root) as port:
            for width, height in ((390, 844), (1280, 900)):
                for theme in ("light", "dark"):
                    run_case(browser, port, width=width, height=height, theme=theme)
            run_case(browser, port, width=390, height=844, theme="light", mode="reduced-motion")
            run_case(browser, port, width=390, height=844, theme="light", mode="forced-colors")
            run_case(browser, port, width=390, height=844, theme="light", mode="touch-assistance")
            run_case(browser, port, width=390, height=844, theme="light", mode="text-200")
            run_case(browser, port, width=390, height=844, theme="light", mode="reduced-transparency")
            run_case(browser, port, width=390, height=844, theme="light", mode="increased-contrast")
    print("GoreeCloud Tasks representative GLAZE UI V1.0 rendered acceptance passed")


if __name__ == "__main__":
    main()
