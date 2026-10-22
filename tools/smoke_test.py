"""Browser checks for the existing portfolio. Optional tooling: Playwright.
Run: python3 tools/smoke_test.py (uses installed Chromium or CHROMIUM_PATH).
"""
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


class PortfolioChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(ROOT)))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'
        cls.playwright = sync_playwright().start()
        options = {'headless': True, 'args': ['--no-sandbox']}
        executable = os.environ.get('CHROMIUM_PATH') or shutil.which('chromium')
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
        self.page.on('pageerror', lambda e: self.errors.append(str(e)))
        self.page.goto(self.base, wait_until='networkidle')

    def tearDown(self):
        self.context.close()
        self.assertEqual(self.errors, [])

    def filter(self, name, count):
        self.page.locator(f'[data-filter="{name}"]').click()
        expect(self.page.locator('.gallery-item:not(.filter-gone)')).to_have_count(count)

    def open(self, index=0):
        self.page.locator('.gallery-item:not(.filter-gone)').nth(index).click()
        expect(self.page.locator('#lightbox')).to_be_visible()
        self.page.wait_for_function('document.querySelector("#lb-img").complete && document.querySelector("#lb-img").naturalWidth > 0')

    def test_01_original_sections_and_design_preserved(self):
        expect(self.page).to_have_title('CriSpy | 3D Portfolio')
        expect(self.page.locator('.hero h1')).to_have_text('Привет,Я Криспи!')
        self.assertEqual(self.page.locator('.gallery-item').count(), 15)
        self.assertEqual(self.page.locator('.review-card').count(), 2)
        self.assertEqual(self.page.locator('.service-row').count(), 5)
        self.assertEqual(self.page.evaluate('getComputedStyle(document.documentElement).getPropertyValue("--orange").trim()'), '#FF6A00')
        self.assertEqual(self.page.locator('.hero-inner').evaluate('el=>getComputedStyle(el).gridTemplateColumns'), '420px 632px')

    def test_02_category_counts_and_rapid_filter_changes(self):
        for name, count in [('head-basic', 2), ('head-models', 2), ('medium', 5), ('big', 5), ('all', 15)]:
            self.filter(name, count)
        self.page.evaluate('''() => {
            document.querySelector('[data-filter="head-basic"]').click();
            document.querySelector('[data-filter="medium"]').click();
            document.querySelector('[data-filter="big"]').click();
        }''')
        expect(self.page.locator('.gallery-item:not(.filter-gone)')).to_have_count(5)
        expect(self.page.locator('.filter-pill.active')).to_have_attribute('data-filter', 'big')
        self.assertEqual(self.page.locator('.gallery-item:not(.filter-gone)').evaluate_all('els=>els.every(el=>el.dataset.category==="big")'), True)

    def test_03_filtered_arrows_and_wraparound(self):
        self.filter('head-basic', 2)
        self.open()
        expect(self.page.locator('#lb-counter')).to_have_text('1 / 2')
        expect(self.page.locator('.lightbox-thumb')).to_have_count(2)
        self.page.keyboard.press('ArrowRight')
        expect(self.page.locator('#lb-counter')).to_have_text('2 / 2')
        expect(self.page.locator('#lb-caption')).to_have_text('Медовая голова')
        self.page.keyboard.press('ArrowRight')
        expect(self.page.locator('#lb-counter')).to_have_text('1 / 2')
        self.page.keyboard.press('ArrowLeft')
        expect(self.page.locator('#lb-counter')).to_have_text('2 / 2')

    def test_04_thumbnail_original_and_order_link(self):
        self.open()
        self.page.locator('.lightbox-thumb').nth(11).click()
        expect(self.page.locator('#lb-caption')).to_have_text('Парень у костра')
        expect(self.page.locator('#lb-counter')).to_have_text('12 / 15')
        expect(self.page.locator('.lightbox-thumb[aria-current="true"]')).to_have_count(1)
        expect(self.page.locator('#lb-original')).to_have_attribute('href', 'render12.jpg')
        text = parse_qs(urlparse(self.page.locator('#lb-order').get_attribute('href')).query)['text'][0]
        self.assertIn('Парень у костра', text)
        self.assertTrue(self.page.locator('#lb-order').get_attribute('href').startswith('https://t.me/Yappy_CriSpy?text='))

    def test_05_original_is_loaded_only_on_zoom(self):
        originals = []
        self.page.on('request', lambda r: originals.append(r.url) if r.url.endswith('/render1.png') else None)
        self.open()
        self.assertEqual(originals, [])
        self.page.locator('#lb-zoom').click()
        expect(self.page.locator('#lb-zoom')).to_have_attribute('aria-pressed', 'true')
        expect(self.page.locator('#lb-img')).to_have_attribute('src', 'render1.png')
        self.page.wait_for_function('document.querySelector("#lb-img").naturalWidth === 1920')
        self.assertEqual(len(originals), 1)
        self.page.locator('#lb-zoom').click()
        expect(self.page.locator('#lb-zoom')).to_have_attribute('aria-pressed', 'false')
        expect(self.page.locator('#lb-img')).to_have_attribute('src', 'media/previews/render1-1600.webp')

    def test_06_focus_keyboard_open_escape_and_restore(self):
        card = self.page.locator('.gallery-item').first
        card.focus()
        self.page.keyboard.press('Enter')
        expect(self.page.locator('#lb-close')).to_be_focused()
        for _ in range(22):
            self.page.keyboard.press('Tab')
            self.assertTrue(self.page.evaluate('document.querySelector("#lightbox").contains(document.activeElement)'))
        self.page.keyboard.press('Escape')
        expect(self.page.locator('#lightbox')).not_to_be_visible()
        expect(card).to_be_focused()
        self.assertEqual(self.page.evaluate('document.body.style.overflow'), '')
        self.page.keyboard.press('Space')
        expect(self.page.locator('#lightbox')).to_be_visible()

    def test_07_portrait_square_and_landscape_fit_viewer(self):
        self.open()
        for width, height in [(1440, 1000), (390, 844), (320, 568), (844, 390)]:
            self.page.set_viewport_size({'width': width, 'height': height})
            for index in [0, 4, 8, 13]:
                self.page.locator('.lightbox-thumb').nth(index).evaluate('el=>el.click()')
                self.page.wait_for_function('document.querySelector("#lb-img").complete && document.querySelector("#lb-img").naturalWidth>0')
                result = self.page.evaluate('''() => {
                    const box=document.querySelector('#lightbox'),img=document.querySelector('#lb-img').getBoundingClientRect(), stage=document.querySelector('#lb-viewport').getBoundingClientRect();
                    return {overflow:box.scrollWidth>box.clientWidth,above:img.top<0,below:img.bottom>innerHeight+1,
                        tooWide:img.width>stage.width+1,tooTall:img.height>stage.height+1};
                }''')
                self.assertFalse(any(result.values()), (width, height, index, result))

    def test_08_mobile_menu_size_inertness_escape_and_order(self):
        self.page.set_viewport_size({'width': 390, 'height': 844})
        menu, burger = self.page.locator('#mobile-nav'), self.page.locator('#burger')
        self.assertTrue(menu.evaluate('el=>el.inert'))
        burger.click()
        expect(burger).to_have_attribute('aria-expanded', 'true')
        self.page.wait_for_function('document.querySelector("#mobile-nav").getBoundingClientRect().height > 200')
        order = menu.get_by_role('link', name='Заказать')
        expect(order).to_be_visible()
        self.assertFalse(menu.evaluate('el=>el.inert'))
        self.page.keyboard.press('Escape')
        expect(burger).to_be_focused()
        self.assertTrue(menu.evaluate('el=>el.inert'))
        burger.click()
        self.page.locator('#mobile-nav a[href="#services"]').click()
        expect(burger).to_have_attribute('aria-expanded', 'false')
        burger.click()
        self.page.set_viewport_size({'width': 1100, 'height': 844})
        expect(burger).to_have_attribute('aria-expanded', 'false')

    def test_09_responsive_widths_and_reachable_prices(self):
        for width in [320, 360, 390, 640, 768, 900, 1024, 1440]:
            self.page.set_viewport_size({'width': width, 'height': 844})
            self.assertFalse(self.page.evaluate('document.documentElement.scrollWidth>innerWidth'), width)
            self.assertTrue(self.page.locator('.services-card').evaluate('el=>el.scrollWidth<=el.clientWidth'), width)
            self.assertTrue(self.page.locator('.reviews-grid').evaluate('el=>el.scrollWidth<=el.clientWidth'), width)

    def test_10_order_buttons_use_correct_telegram(self):
        for selector in ['.nav-cta', '.mobile-nav-cta-wrap a', '#contact']:
            expect(self.page.locator(selector)).to_have_attribute('href', 'https://t.me/Yappy_CriSpy')
        self.assertEqual(self.page.locator('a').evaluate_all('els=>els.filter(el=>el.textContent.trim()==="Заказать" && el.getAttribute("href")==="#").length'), 0)

    def test_11_swipe_and_pinch_do_not_conflict(self):
        self.open()
        self.page.locator('#lb-viewport').evaluate('''el=>{
            const point=(x,id=1)=>new Touch({identifier:id,target:el,clientX:x,clientY:100});
            el.dispatchEvent(new TouchEvent('touchstart',{touches:[point(250)]}));
            el.dispatchEvent(new TouchEvent('touchend',{changedTouches:[point(100)]}));
        }''')
        expect(self.page.locator('#lb-counter')).to_have_text('2 / 15')
        self.page.locator('#lb-viewport').evaluate('''el=>{
            const point=(x,id)=>new Touch({identifier:id,target:el,clientX:x,clientY:100});
            el.dispatchEvent(new TouchEvent('touchstart',{touches:[point(250,1),point(200,2)]}));
            el.dispatchEvent(new TouchEvent('touchend',{changedTouches:[point(100,1)]}));
        }''')
        expect(self.page.locator('#lb-counter')).to_have_text('2 / 15')

    def test_12_loading_error_offers_original(self):
        self.page.route('**/render1-1600.webp', lambda route: route.abort())
        self.page.locator('.gallery-item').first.click()
        expect(self.page.locator('#lb-feedback')).to_contain_text('Не удалось загрузить')
        expect(self.page.locator('#lb-feedback a')).to_have_attribute('href', 'render1.png')
        self.page.keyboard.press('ArrowRight')
        self.page.wait_for_function('document.querySelector("#lb-img").naturalWidth>0')
        expect(self.page.locator('#lb-feedback')).not_to_be_visible()

    def test_13_all_page_assets_are_local_and_load(self):
        external, failed = [], []
        self.page.on('request', lambda r: external.append(r.url) if not r.url.startswith(self.base) else None)
        self.page.on('response', lambda r: failed.append(r.url) if r.status>=400 else None)
        self.page.reload(wait_until='networkidle')
        self.page.evaluate("document.querySelectorAll('img').forEach(el=>el.loading='eager')")
        self.page.wait_for_function("[...document.images].filter(el=>el.getAttribute('src')).every(el=>el.complete&&el.naturalWidth>0)")
        self.assertEqual(external, [])
        self.assertEqual(failed, [])
        self.assertTrue(self.page.evaluate("document.fonts.check('16px Manrope') && document.fonts.check('16px \"Bebas Neue\"')"))

    def test_14_reduced_motion_and_no_javascript_content(self):
        self.page.emulate_media(reduced_motion='reduce')
        self.page.reload(wait_until='networkidle')
        self.assertEqual(self.page.evaluate('getComputedStyle(document.documentElement).scrollBehavior'), 'auto')
        self.assertEqual(self.page.locator('.availability-dot').evaluate('el=>getComputedStyle(el,"::after").animationName'), 'none')
        self.assertEqual(self.page.locator('.reveal').first.evaluate('el=>getComputedStyle(el).opacity'), '1')
        context = self.browser.new_context(java_script_enabled=False)
        try:
            page = context.new_page()
            page.goto(self.base, wait_until='networkidle')
            self.assertEqual(page.locator('.reveal').first.evaluate('el=>getComputedStyle(el).opacity'), '1')
            expect(page.locator('#lightbox')).not_to_be_visible()
            expect(page.locator('.nav-cta')).to_have_attribute('href', 'https://t.me/Yappy_CriSpy')
            self.assertEqual(page.locator('.gallery-item').count(), 15)
        finally:
            context.close()

    def test_15_reviews_open_correct_render_with_filter(self):
        self.filter('head-basic', 2)
        review = self.page.locator('.review-card').first
        review.click()
        expect(self.page.locator('#lb-caption')).to_have_text('Подводный мир')
        expect(self.page.locator('#lb-counter')).to_have_text('1 / 15')
        self.page.keyboard.press('Escape')
        expect(review).to_be_focused()

    def test_16_gallery_and_review_toggles(self):
        for button, target in [('#gallery-toggle', '#gallery-wrap'), ('#reviews-toggle', '#reviews-wrap')]:
            self.page.locator(button).click()
            expect(self.page.locator(button)).to_have_attribute('aria-expanded', 'false')
            expect(self.page.locator(target)).to_have_class('gallery-wrap collapsed' if target=='#gallery-wrap' else 'reviews-wrap collapsed')
            self.page.locator(button).click()
            expect(self.page.locator(button)).to_have_attribute('aria-expanded', 'true')


if __name__ == '__main__':
    unittest.main(verbosity=2)
