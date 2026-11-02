# Startup, pagination, and shell verification

Verification date: 2026-11-02 (Asia/Singapore). Latest verified implementation: `5e0d2da`; original timing baseline: `42b55a6`.

## Scope and environment

This report covers Task 6 of the 2026-10-28 startup/pagination/shell plan. Local execution uses Windows and Python 3.11.0, rather than the plan's proposed Python 3.12. Tests use real Tk. This is source execution, not a packaged Release build. The original focused and full suites at `42b55a6` ran concurrently; their elapsed durations are regression evidence under shared load, not performance benchmarks. Timing samples ran only after both original suites finished. A fresh serial full-suite run covers subsequent commits `4781bb6` (enlarged-text wrapping), `7539cb7` (deferred preview error recovery), and `5e0d2da` (enlarged-text new-badge containment), with no concurrent GUI tests.

The user explicitly approved a fully themed custom title bar on Windows and retention of native title bars on macOS and Linux for this delivery, preserving existing platform behavior. The custom client-drawn frame is Windows-only; macOS/Linux retain their native decoration without duplicate custom controls. No macOS/Linux GUI execution or remote GitHub Actions matrix is claimed here, so their behavior was not verified in this run.

## Regression commands

Executed from the worktree root, with workspace-local temporary storage:

```powershell
$testTemp = Join-Path (Get-Location) '.test-tmp'
New-Item -ItemType Directory -Force -Path $testTemp | Out-Null
$env:TEMP = $testTemp
$env:TMP = $testTemp
python -m unittest tests.test_pagination tests.test_window_chrome tests.test_settings_window tests.test_wardrobe tests.test_wardrobe_integration tests.test_startup_performance -v
python scripts/run_ci_tests.py
git diff --check
```

| Check | Result |
| --- | --- |
| Original focused UI suite (`42b55a6`) | 151 tests, 241.608 s, OK, exit 0 |
| Original full CI-equivalent (`42b55a6`) | 445 tests, 287.066 s, OK (18 skips), exit 0 |
| Final serial full CI-equivalent (`5e0d2da`) | 451 tests, 222.474 s, OK (18 skips), exit 0 |
| `git diff --check` | Exit 0, no diagnostics |

The final full-suite run executed `python scripts/run_ci_tests.py` alone, after the coordinator confirmed other GUI suites had finished. It includes all focused UI modules; the standalone focused command was not separately rerun at the final head. An earlier post-fix CI attempt was interrupted before its result to avoid overlap with reviewer GUI checks and is not counted as verification evidence.

The 18 skips in both completed CI runs are platform-appropriate: three macOS window-manager tests, three Xorg keyboard tests, one Linux work-area test, one macOS work-area test, and ten Linux portable staging tests. Linux-only integration is conditionally added by the runner only on Linux, so it did not run here. Logs also contained Google Drive registry-key access diagnostics; no unittest failure resulted. The focused helper printed 0.1138 s shell construction and 2.295 s shell/navigation under concurrent test load; the isolated measurements below are the performance evidence.

## Construction, pagination, and layout evidence

The startup construction regression asserts zero `load_frame` calls across Settings, Wardrobe, and Achievements during initial shell construction. Metrics, Wardrobe, Achievements, and Settings preview widgets do not exist until their deferred paths run. First Metrics navigation builds it; the next navigation reuses the same instance. The first mapped rail has the selected-cat placeholder, no rendered preview calls, and an invokable navigation action. Preview hydration loads one pose per idle step; close cancels owned pending callbacks.

Collection regressions check active-slice-only mounting, four-card normal/two-card compact behavior, page clamping, off-page focus, equipped-state preservation, progress and new-reward state. The Achievements fixture has 22 visible rewards, equivalent to six normal pages or eleven compact pages. Wardrobe fixtures check slice identity and the four-card mounting bound; unlock-dependent totals are not assumed constant.

Real-Tk bounds tests cover shelf/card content and pager containment, scrollbar reachability, measured wrapping, narrow layouts, and scaled layout behavior. A separate native visual inspection by the coordinating agent at 920x1360 confirmed Settings title bar/shelves, four complete Wardrobe cards and pager on both pages 1 and 2 (items 1-4 and 5-8), and a 2x2 Achievements page with pager. A geometry reviewer additionally checked live Tk bounds at 920x1360, 620x500, and 920x800. Compact/high-DPI screenshots, physical taskbar interaction, pointer dragging/resizing, and other operating systems were not visually verified in this run. Automated Windows tests exercise native resize-edge hit testing, minimize/restore, maximize/restore, system-close routing, native styles/taskbar identity, and Tk wrapper recreation; these do not substitute for physical pointer and taskbar checks.

The final suite adds real-Tk regressions at scaling 2.5 and 620x700 geometry for Wardrobe label wrapping, action/card/pager containment, and complete new-badge visibility without status overlap across page changes. Preview error tests cover transient renderer recovery, bounded persistent PhotoImage failure with visible user retry, SVG parser failures, and close-time retry cancellation. These are automated geometry/error-injection checks; they do not add physical high-DPI or failure-state screenshots.

## Timing method and limitations

The timings below were collected at `42b55a6`, before the enlarged-text wrapping, new-badge containment, and preview recovery fixes. They are historical measurements of that implementation; they have not been rerun at `5e0d2da` and must not be presented as final-head performance results.

Five fresh Python processes provide process-cold samples; they do not flush the OS filesystem cache or measure reboot-cold startup. One separate Python process performs one discarded priming run, then five retained warm runs with shared Python/render caches and fresh Tk roots/app instances. Imports precede the app-init timer, so process launch/import time is excluded. Profiles live under workspace TEMP; keyboard hooks, tray and event-loop monitoring are not started, and update checking is not invoked. App initialization and `open_settings` use their real constructors; no renderer mocks or instrumentation patches are used.

`open return` measures synchronous `open_settings()` return. `Mapped interactive` measures from its invocation through the rail's first `<Map>` event and invokes the Settings navigation button there; this is a Tk mapping/action proxy for the first interactive frame, not a compositor presentation or input-latency trace. `Initial idle drain` measures until the following `root.update()` returns, including deferred shelves/preview/overlay work. The shell proxy is intentionally distinguished from complete preview readiness. Navigation is measured in Metrics → Wardrobe → Achievements order through `update_idletasks()`, including geometry/render work but not a presented-frame guarantee. Each warm navigation returns to Settings first and reuses its constructed destination.

All retained samples mounted four Wardrobe tiles and four Achievement cards. Measurements ran after both suites finished. The focused and CI test processes were no longer running during timing collection; other desktop/OS activity remains uncontrolled. Warm samples include a 415.783 ms app-init outlier and a 445.711 ms first-Achievements sample; neither is discarded. No performance threshold or statistically controlled before/after improvement is claimed. The old design's 1.3–1.8 s first-open figure used a different endpoint, so it is not a direct ratio comparison.

All table values are milliseconds (rounded to 0.001 ms for reproducible aggregation, not a claim of measurement accuracy).

| Sample | App init | open return | Mapped interactive | Initial idle drain | First Metrics | First Wardrobe | First Achievements | Warm Metrics | Warm Wardrobe | Warm Achievements |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Cold 1 | 187.448 | 55.119 | 112.746 | 1143.204 | 263.246 | 584.387 | 218.775 | 145.203 | 109.744 | 195.810 |
| Cold 2 | 193.712 | 56.019 | 110.195 | 1215.157 | 210.332 | 600.756 | 220.888 | 143.817 | 108.732 | 191.685 |
| Cold 3 | 193.759 | 56.098 | 110.872 | 1191.256 | 210.946 | 613.662 | 213.888 | 141.652 | 107.334 | 213.526 |
| Cold 4 | 193.079 | 55.765 | 110.188 | 1196.963 | 207.583 | 622.525 | 216.731 | 143.207 | 109.120 | 209.149 |
| Cold 5 | 191.186 | 54.535 | 109.346 | 1184.618 | 255.018 | 628.852 | 216.862 | 152.260 | 114.753 | 199.536 |
| Warm 1 | 139.928 | 59.673 | 79.961 | 935.985 | 157.153 | 562.134 | 445.711 | 106.445 | 249.314 | 298.385 |
| Warm 2 | 415.783 | 114.988 | 147.663 | 1108.289 | 153.840 | 470.382 | 222.423 | 109.135 | 203.712 | 142.118 |
| Warm 3 | 159.142 | 64.525 | 83.989 | 854.965 | 155.278 | 439.974 | 206.778 | 109.005 | 165.501 | 162.214 |
| Warm 4 | 140.384 | 63.402 | 89.418 | 1334.667 | 174.279 | 456.533 | 208.431 | 111.297 | 169.544 | 141.821 |
| Warm 5 | 138.635 | 59.399 | 78.504 | 835.079 | 161.284 | 480.969 | 279.115 | 106.069 | 165.022 | 146.895 |

| Metric | Cold median | Cold worst | Warm median | Warm worst |
| --- | ---: | ---: | ---: | ---: |
| App init | 193.079 | 193.759 | 140.384 | 415.783 |
| open return | 55.765 | 56.098 | 63.402 | 114.988 |
| Mapped interactive | 110.195 | 112.746 | 83.989 | 147.663 |
| Initial idle drain | 1191.256 | 1215.157 | 935.985 | 1334.667 |
| First Metrics | 210.946 | 263.246 | 157.153 | 174.279 |
| First Wardrobe | 613.662 | 628.852 | 470.382 | 562.134 |
| First Achievements | 216.862 | 220.888 | 222.423 | 445.711 |
| Warm Metrics | 143.817 | 152.260 | 109.005 | 111.297 |
| Warm Wardrobe | 109.120 | 114.753 | 169.544 | 249.314 |
| Warm Achievements | 199.536 | 213.526 | 146.895 | 298.385 |


## Reproduction harness

Save the following as `.test-tmp/benchmark.py`; run five fresh processes, then one process with one discarded priming run and five retained warm runs:

```powershell
1..5 | ForEach-Object { python .test-tmp/benchmark.py cold $_ }
python .test-tmp/benchmark.py warm
```

```python
import json, sys, time, platform
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cat_type import CatTypeApp
from cat_settings import AppSettings, SettingsStore

def sample(kind, index):
    t=time.perf_counter()
    app=CatTypeApp(settings=AppSettings(), settings_store=SettingsStore(Path(__file__).parent / 'benchmark-profile' / f'{kind}-{index}' / 'settings.json'))
    init=time.perf_counter()-t
    t=time.perf_counter(); app.open_settings(); shell=time.perf_counter()-t
    view=app._settings_window
    marker=[]
    def mapped(event):
        if event.widget is view.rail_preview and not marker:
            marker.append(time.perf_counter()-t)
            view.page_buttons['Settings'].invoke()
    view.rail_preview.bind('<Map>', mapped, add='+')
    app.root.update()
    hydration=time.perf_counter()-t
    nav={}; warm={}
    for name in ('Metrics','Wardrobe','Achievements'):
        start=time.perf_counter(); view.page_buttons[name].invoke(); app.root.update_idletasks(); nav[name]=time.perf_counter()-start
        view.page_buttons['Settings'].invoke(); app.root.update_idletasks()
        start=time.perf_counter(); view.page_buttons[name].invoke(); app.root.update_idletasks(); warm[name]=time.perf_counter()-start
    result=dict(kind=kind,index=index,init=init,shell=shell,interactive=marker[0] if marker else None,hydration=hydration,first_nav=nav,warm_nav=warm,wardrobe_cards=len(view.wardrobe.buttons),achievement_cards=len(view.achievements.cards))
    view.close(); app.shutdown()
    return result
if __name__=='__main__':
    if sys.argv[1]=='cold':
        print(json.dumps(sample('cold',int(sys.argv[2]))))
    else:
        sample('prewarm',0)
        for i in range(1,6): print(json.dumps(sample('warm',i)))
```
