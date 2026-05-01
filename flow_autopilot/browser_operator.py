from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time

from .models import AppSettings


class BrowserOperatorError(RuntimeError):
    pass


@dataclass
class FlowBrowserOperator:
    settings: AppSettings
    workspace: Path

    def _import_playwright(self):
        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise BrowserOperatorError(
                "Playwright не установлен. Выполни: pip install -r requirements.txt && playwright install chromium"
            ) from exc
        return sync_playwright, PlaywrightTimeoutError

    def _profile_dir(self) -> Path:
        profile = Path(self.settings.chrome_profile_dir)
        if not profile.is_absolute():
            profile = self.workspace / profile
        profile.mkdir(parents=True, exist_ok=True)
        return profile

    def send_prompt(self, prompt: str) -> None:
        sync_playwright, PlaywrightTimeoutError = self._import_playwright()
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(self._profile_dir()),
                headless=False,
                channel="chrome",
                viewport={"width": 1440, "height": 1000},
            )
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(self.settings.flow_url, wait_until="domcontentloaded")
            self._fill_prompt(page, prompt, PlaywrightTimeoutError)
            self._click_generate(page, PlaywrightTimeoutError)
            self.wait_for_generation()
            context.close()

    def save_result_screenshot(self, output_path: Path) -> Path:
        sync_playwright, PlaywrightTimeoutError = self._import_playwright()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(self._profile_dir()),
                headless=False,
                channel="chrome",
                viewport={"width": 1440, "height": 1000},
            )
            page = context.pages[0] if context.pages else context.new_page()
            if not page.url or page.url == "about:blank":
                page.goto(self.settings.flow_url, wait_until="domcontentloaded")
            if self.settings.result_selector:
                try:
                    locator = page.locator(self.settings.result_selector).last
                    locator.wait_for(timeout=10_000)
                    locator.screenshot(path=str(output_path))
                    context.close()
                    return output_path
                except PlaywrightTimeoutError:
                    pass
            page.screenshot(path=str(output_path), full_page=True)
            context.close()
            return output_path

    def wait_for_generation(self) -> None:
        seconds = max(1, int(self.settings.generation_wait_seconds))
        time.sleep(seconds)

    def _fill_prompt(self, page, prompt: str, timeout_error) -> None:
        selectors = [
            self.settings.prompt_field_selector,
            "textarea",
            "[contenteditable='true']",
            "div[role='textbox']",
        ]
        for selector in [item for item in selectors if item]:
            try:
                locator = page.locator(selector).last
                locator.wait_for(timeout=12_000)
                locator.click()
                try:
                    locator.fill(prompt)
                except Exception:
                    page.keyboard.press("Control+A")
                    page.keyboard.type(prompt)
                return
            except Exception:
                continue
        raise BrowserOperatorError("Не нашел поле промпта во Flow. Задай Prompt field selector в настройках.")

    def _click_generate(self, page, timeout_error) -> None:
        if self.settings.generate_button_selector:
            try:
                page.locator(self.settings.generate_button_selector).last.click(timeout=10_000)
                return
            except Exception:
                pass
        labels = ["Generate", "Generate image", "Создать", "Сгенерировать"]
        for label in labels:
            try:
                page.get_by_role("button", name=label).last.click(timeout=5_000)
                return
            except Exception:
                continue
        try:
            page.keyboard.press("Enter")
            return
        except Exception as exc:
            raise BrowserOperatorError("Не нашел кнопку генерации во Flow. Задай Generate button selector.") from exc
