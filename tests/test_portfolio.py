"""Browser regression tests. Run: python3 -m unittest discover -s tests -v"""
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import shutil
import threading
import unittest
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class PortfolioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(
            ('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(ROOT)))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'
        cls.playwright = sync_playwright().start()
        executable = os.environ.get('CHROMIUM_PATH') or shutil.which('chromium')
        options = {'headless': True, 'args': ['--no-sandbox']}
        if executable:
            options['executable_path'] = executable
        cls.browser = cls.playwright.chromium.launch(**options)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        self.context = self.browser.new_context(viewport={'width': 1440, 'height': 1000})
        self.page = self.context.new_page()
        self.errors = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))

    def tearDown(self):
        self.context.close()
        self.assertEqual(self.errors, [], 'Unexpected JavaScript errors')

    def load(self, query=''):
        response = self.page.goto(self.base + '/' + query, wait_until='networkidle')
        self.assertEqual(response.status, 200)
        self.page.evaluate('document.fonts.ready')

    def test_01_curated_selection_and_expand(self):
        self.load()
        expect(self.page.locator('.work-card:visible')).to_have_count(5)
        self.page.locator('#show-more').click()
        expect(self.page.locator('.work-card:visible')).to_have_count(15)
        expect(self.page.locator('#show-more')).to_have_attribute('aria-expanded', 'true')
        self.page.locator('#show-more').click()
        expect(self.page.locator('.work-card:visible')).to_have_count(5)

    def test_02_category_counts(self):
        self.load()
        for category, count in [('scenes', 10), ('avatars', 4), ('experiments', 1)]:
            self.page.locator(f'[data-filter="{category}"]').click()
            expect(self.page.locator('.work-card:visible')).to_have_count(count)
            expect(self.page.locator(f'[data-filter="{category}"]')).to_have_attribute('aria-pressed', 'true')
            self.assertEqual(parse_qs(urlparse(self.page.url).query)['filter'], [category])

    def test_03_search_normalization_and_empty_reset(self):
        self.load()
        search = self.page.locator('#work-search')
        search.fill('ЗАНУДНАЯ УЧЕБА')
        expect(self.page.locator('.work-card:visible')).to_have_count(1)
        expect(self.page.locator('.work-card:visible')).to_have_attribute('data-id', 'render11')
        search.fill('<script>alert(1)</script>')
        expect(self.page.locator('#empty-state')).to_be_visible()
        self.page.locator('#reset-filters').click()
        expect(search).to_have_value('')
        expect(self.page.locator('.work-card:visible')).to_have_count(5)

    def test_04_favorites_persist_and_empty_state(self):
        self.load()
        self.page.locator('[data-favorite="render1"]').click()
        expect(self.page.locator('#favorites-count')).to_have_text('1')
        self.page.locator('[data-filter="favorites"]').click()
        expect(self.page.locator('.work-card:visible')).to_have_count(1)
        self.page.reload(wait_until='networkidle')
        expect(self.page.locator('[data-favorite="render1"]')).to_have_attribute('aria-pressed', 'true')
        self.page.locator('[data-favorite="render1"]').click()
        expect(self.page.locator('#empty-state')).to_be_visible()
        expect(self.page.locator('#favorites-count')).to_have_text('0')

    def test_05_blocked_storage_is_nonfatal(self):
        self.page.add_init_script("Object.defineProperty(window, 'localStorage', {get(){throw new Error('Blocked')}})")
        self.load()
        self.page.locator('[data-favorite="render1"]').click()
        expect(self.page.locator('#favorites-count')).to_have_text('1')
        expect(self.page.locator('#toast')).to_contain_text('до закрытия страницы')
        self.page.locator('[data-filter="favorites"]').click()
        expect(self.page.locator('.work-card:visible')).to_have_count(1)

    def test_06_lightbox_keyboard_zoom_and_focus(self):
        self.load()
        trigger = self.page.locator('[data-open="render1"]').first
        trigger.click()
        expect(self.page.locator('#lightbox')).to_be_visible()
        expect(self.page.locator('#lb-close')).to_be_focused()
        expect(self.page.locator('#lb-counter')).to_have_text('1 / 15')
        self.page.wait_for_function('document.querySelector("#lb-img").naturalWidth > 0')
        self.page.keyboard.press('ArrowRight')
        expect(self.page.locator('#lb-title')).to_have_text('Парень у костра')
        self.page.locator('#lb-zoom').click()
        expect(self.page.locator('#lb-zoom')).to_have_attribute('aria-pressed', 'true')
        self.page.locator('#lb-favorite').click()
        expect(self.page.locator('#lb-favorite')).to_have_attribute('aria-pressed', 'true')
        self.page.keyboard.press('Escape')
        expect(self.page.locator('#lightbox')).not_to_be_visible()
        expect(trigger).to_be_focused()
        self.assertNotIn('work=', self.page.url)

    def test_07_filtered_lightbox_wraps_in_category(self):
        self.load('?filter=avatars')
        self.page.locator('[data-open="render5"]').first.click()
        expect(self.page.locator('#lb-counter')).to_have_text('1 / 4')
        self.page.keyboard.press('ArrowLeft')
        expect(self.page.locator('#lb-counter')).to_have_text('4 / 4')
        expect(self.page.locator('#lb-category')).to_contain_text('Аватар')
        self.page.keyboard.press('ArrowRight')
        expect(self.page.locator('#lb-counter')).to_have_text('1 / 4')

    def test_08_deep_link_and_invalid_query(self):
        self.load('?work=render9&filter=avatars')
        expect(self.page.locator('#lightbox')).to_be_visible()
        expect(self.page.locator('#lb-title')).to_have_text('Холодный апокалипсис')
        self.page.keyboard.press('Escape')
        self.load('?filter=unknown&work=missing')
        expect(self.page.locator('#lightbox')).not_to_be_visible()
        expect(self.page.locator('.work-card:visible')).to_have_count(5)

    def test_09_mobile_menu_and_responsive_widths(self):
        self.load()
        for width in [320, 390, 620, 768, 1024, 1440]:
            self.page.set_viewport_size({'width': width, 'height': 844})
            self.assertFalse(self.page.evaluate('document.documentElement.scrollWidth > innerWidth'), width)
        self.page.set_viewport_size({'width': 390, 'height': 844})
        burger = self.page.locator('#burger')
        burger.click()
        expect(self.page.locator('#mobile-nav')).to_be_visible()
        self.page.keyboard.press('Escape')
        expect(burger).to_be_focused()
        expect(self.page.locator('#mobile-nav')).not_to_be_visible()
        burger.click()
        self.page.locator('#mobile-nav a[href="#services"]').click()
        expect(burger).to_have_attribute('aria-expanded', 'false')
        self.page.locator('#burger').click()
        self.page.set_viewport_size({'width': 1024, 'height': 844})
        self.page.set_viewport_size({'width': 390, 'height': 844})
        expect(self.page.locator('#mobile-nav')).not_to_be_visible()

    def test_10_calculator_telegram_brief_and_bounds(self):
        self.load()
        expect(self.page.locator('#order-price')).to_have_text('от 30 ₽')
        expect(self.page.locator('#extra-characters')).not_to_be_visible()
        self.page.locator('[data-service="big"]').click()
        self.page.locator('#characters-plus').click()
        self.page.locator('#characters-plus').click()
        expect(self.page.locator('#order-price')).to_have_text('от 140 ₽')
        self.page.locator('#order-idea').fill('Ночной лес & костёр 🔥')
        query = parse_qs(urlparse(self.page.locator('#order-link').get_attribute('href')).query)
        self.assertIn('Дополнительных персонажей: 2.', query['text'][0])
        self.assertIn('Ночной лес & костёр 🔥', query['text'][0])
        self.assertIn('от 140 ₽', query['text'][0])
        self.page.locator('#characters').fill('100')
        expect(self.page.locator('#characters')).to_have_value('20')
        expect(self.page.locator('#characters-plus')).to_be_disabled()
        self.page.locator('#characters').fill('-5')
        expect(self.page.locator('#characters')).to_have_value('0')
        expect(self.page.locator('#characters-minus')).to_be_disabled()
        self.page.locator('[data-service="head-models"]').click()
        expect(self.page.locator('#extra-characters')).not_to_be_visible()
        expect(self.page.locator('#order-price')).to_have_text('от 50 ₽')

    def test_11_no_external_requests_or_failed_assets(self):
        requests, failed = [], []
        self.page.on('request', lambda request: requests.append(request.url))
        self.page.on('response', lambda response: failed.append(response.url) if response.status >= 400 else None)
        self.load()
        self.page.locator('#show-more').click()
        self.page.evaluate("document.querySelectorAll('img').forEach(img => img.loading = 'eager')")
        self.page.wait_for_function("[...document.images].filter(i=>i.getAttribute('src')).every(i=>i.complete && i.naturalWidth>0)")
        self.assertTrue(requests)
        self.assertEqual(failed, [])
        self.assertTrue(all(url.startswith(self.base) for url in requests))
        self.assertTrue(self.page.evaluate("document.fonts.check('600 20px Manrope') && document.fonts.check('600 20px Unbounded')"))

    def test_12_no_javascript_fallback(self):
        context = self.browser.new_context(java_script_enabled=False)
        try:
            page = context.new_page()
            page.goto(self.base, wait_until='networkidle')
            expect(page.locator('.work-card:visible')).to_have_count(15)
            expect(page.locator('#work-search')).not_to_be_visible()
            expect(page.locator('#order-link')).to_have_attribute('href', 'https://t.me/Yappy_CriSpy')
            page.locator('[data-open="render1"]').first.click()
            self.assertTrue(page.url.endswith('/render1.png'))
        finally:
            context.close()

    def test_13_reduced_motion(self):
        self.page.emulate_media(reduced_motion='reduce')
        self.load()
        self.assertEqual(self.page.evaluate('getComputedStyle(document.documentElement).scrollBehavior'), 'auto')
        self.assertEqual(self.page.locator('.hero-copy').evaluate('el => getComputedStyle(el).animationName'), 'none')

    def test_14_storage_sync_between_tabs(self):
        self.load()
        other = self.context.new_page()
        other.goto(self.base)
        other.locator('[data-favorite="render1"]').click()
        expect(self.page.locator('#favorites-count')).to_have_text('1')
        other.evaluate('localStorage.clear()')
        expect(self.page.locator('#favorites-count')).to_have_text('0')
        other.close()

    def test_15_dialog_focus_is_trapped(self):
        self.load('?work=render1')
        for _ in range(12):
            self.page.keyboard.press('Tab')
            self.assertTrue(self.page.evaluate('document.querySelector("#lightbox").contains(document.activeElement)'))

    def test_16_no_duplicate_ids_and_control_targets_exist(self):
        self.load()
        self.assertEqual(self.page.locator('h1').count(), 1)
        ids = self.page.locator('[id]').evaluate_all('els=>els.map(el=>el.id)')
        self.assertEqual(len(ids), len(set(ids)))
        for target in self.page.locator('[aria-controls]').evaluate_all('els=>els.map(el=>el.getAttribute("aria-controls"))'):
            self.assertEqual(self.page.locator(f'#{target}').count(), 1)

    def test_17_clipboard_permission_fallback(self):
        self.page.add_init_script("Object.defineProperty(navigator, 'clipboard', {value: {writeText: async()=>{throw Error('denied')}}})")
        self.load()
        self.page.locator('#copy-contact').click()
        expect(self.page.locator('#toast')).to_contain_text('можно скопировать вручную')

    def test_18_touch_swipe_navigation(self):
        self.load('?work=render1')
        self.page.locator('#lb-image-wrap').evaluate('''element => {
            const point = x => new Touch({identifier: 1, target: element, clientX: x, clientY: 150});
            element.dispatchEvent(new TouchEvent('touchstart', {touches: [point(250)]}));
            element.dispatchEvent(new TouchEvent('touchend', {changedTouches: [point(100)]}));
        }''')
        expect(self.page.locator('#lb-counter')).to_have_text('2 / 15')

    def test_19_share_link_clipboard_and_feedback(self):
        self.page.add_init_script("Object.defineProperty(navigator, 'clipboard', {value: {writeText: async text=>{window.copiedText=text}}})")
        self.load('?work=render12')
        self.page.locator('#lb-share').click()
        expect(self.page.locator('.lightbox-hint')).to_have_text('Ссылка на эту работу скопирована.')
        self.assertEqual(parse_qs(urlparse(self.page.evaluate('window.copiedText')).query)['work'], ['render12'])
        self.page.keyboard.press('ArrowRight')
        expect(self.page.locator('#lb-share')).to_have_attribute('aria-label', 'Скопировать ссылку на работу')

    def test_20_favorite_removal_returns_focus(self):
        self.load()
        self.page.locator('[data-favorite="render1"]').click()
        self.page.locator('[data-filter="favorites"]').click()
        self.page.locator('[data-favorite="render1"]').click()
        expect(self.page.locator('[data-filter="favorites"]')).to_be_focused()

    def test_21_mobile_dialog_fits_viewport(self):
        self.page.set_viewport_size({'width': 320, 'height': 640})
        self.load('?work=render9')
        self.assertTrue(self.page.locator('#lightbox').evaluate('el => el.scrollWidth <= el.clientWidth'))
        self.assertFalse(self.page.evaluate('document.documentElement.scrollWidth > innerWidth'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
