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
        self.assertEqual(self.page.locator('.gallery-item').count(), 17)
        self.assertEqual(self.page.locator('.review-card').count(), 2)
        self.assertEqual(self.page.locator('.service-row').count(), 5)
        self.assertEqual(self.page.evaluate('getComputedStyle(document.documentElement).getPropertyValue("--orange").trim()'), '#FF6A00')
        layout = self.page.evaluate('''() => {
            const image=document.querySelector('.hero-img-wrap').getBoundingClientRect();
            const content=document.querySelector('.hero-content').getBoundingClientRect();
            const hero=document.querySelector('.hero').getBoundingClientRect();
            return {imageWidth:image.width, imageRight:image.right, textLeft:content.left, heroHeight:hero.height};
        }''')
        self.assertGreaterEqual(layout['imageWidth'], 320)
        self.assertLessEqual(layout['imageWidth'], 380)
        self.assertLess(layout['imageRight'], layout['textLeft'])
        self.assertLess(layout['heroHeight'], 740)

    def test_02_category_counts_and_rapid_filter_changes(self):
        for name, count in [('head-basic', 2), ('head-models', 2), ('medium', 6), ('big', 6), ('all', 17)]:
            self.filter(name, count)
        self.page.evaluate('''() => {
            document.querySelector('[data-filter="head-basic"]').click();
            document.querySelector('[data-filter="medium"]').click();
            document.querySelector('[data-filter="big"]').click();
        }''')
        expect(self.page.locator('.gallery-item:not(.filter-gone)')).to_have_count(6)
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
        expect(self.page.locator('#lb-counter')).to_have_text('12 / 17')
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
        fitted = self.page.locator('#lb-img').bounding_box()
        self.page.locator('#lb-zoom').click()
        expect(self.page.locator('#lb-zoom')).to_have_attribute('aria-pressed', 'true')
        expect(self.page.locator('#lb-img')).to_have_attribute('src', 'render1.png')
        self.page.wait_for_function('document.querySelector("#lb-img").naturalWidth === 1920')
        self.assertEqual(len(originals), 1)
        self.page.locator('#lb-zoom').click()
        expect(self.page.locator('#lb-zoom')).to_have_attribute('aria-pressed', 'false')
        self.page.wait_for_function("width=>Math.abs(document.querySelector('#lb-img').getBoundingClientRect().width-width)<2", arg=fitted['width'])
        # Keep the decoded original when fitting again; no blank reload or extra download.
        expect(self.page.locator('#lb-img')).to_have_attribute('src', 'render1.png')
        self.assertEqual(len(originals), 1)

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
        self.page.wait_for_function("document.body.style.overflow === ''")
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
        expect(self.page.locator('#lb-counter')).to_have_text('2 / 17')
        self.page.locator('#lb-viewport').evaluate('''el=>{
            const point=(x,id)=>new Touch({identifier:id,target:el,clientX:x,clientY:100});
            el.dispatchEvent(new TouchEvent('touchstart',{touches:[point(250,1),point(200,2)]}));
            el.dispatchEvent(new TouchEvent('touchend',{changedTouches:[point(100,1)]}));
        }''')
        expect(self.page.locator('#lb-counter')).to_have_text('2 / 17')

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
        self.assertTrue(self.page.evaluate("document.fonts.check('16px Onest') && document.fonts.check('16px Rubik')"))

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
            self.assertEqual(page.locator('.gallery-item').count(), 17)
        finally:
            context.close()

    def test_15_reviews_open_correct_render_with_filter(self):
        self.filter('head-basic', 2)
        review = self.page.locator('.review-card').first
        review.click()
        expect(self.page.locator('#lb-caption')).to_have_text('Подводный мир')
        expect(self.page.locator('#lb-counter')).to_have_text('1 / 17')
        self.page.keyboard.press('Escape')
        expect(review).to_be_focused()

    def test_16_gallery_and_review_toggles(self):
        for button, target in [('#gallery-toggle', '#gallery-wrap'), ('#reviews-toggle', '#reviews-wrap')]:
            self.page.locator(button).click()
            expect(self.page.locator(button)).to_have_attribute('aria-expanded', 'false')
            expect(self.page.locator(target)).to_have_class('gallery-wrap collapsed' if target=='#gallery-wrap' else 'reviews-wrap collapsed')
            self.page.locator(button).click()
            expect(self.page.locator(button)).to_have_attribute('aria-expanded', 'true')

    def test_17_street_layer_is_decorative_and_fonts_load(self):
        expect(self.page.locator('.comet-slot')).to_have_count(3)
        expect(self.page.locator('.hero-star')).to_have_count(1)
        expect(self.page.locator('.street-backdrop')).to_have_attribute('aria-hidden', 'true')
        self.assertTrue(self.page.locator('.street-backdrop').evaluate('e=>e.inert'))
        self.assertEqual(self.page.locator('.street-backdrop').evaluate('e=>getComputedStyle(e).pointerEvents'), 'none')
        self.assertLess(self.page.locator('.hero-star').bounding_box()['x'], self.page.locator('.hero-img-wrap').bounding_box()['x'])
        self.page.evaluate('document.fonts.ready')
        self.assertIn('Onest', self.page.locator('body').evaluate('e=>getComputedStyle(e).fontFamily'))
        self.assertIn('Rubik', self.page.locator('h1').evaluate('e=>getComputedStyle(e).fontFamily'))
        # External SVG fragments must refer to real symbols in the shipped sprite.
        import xml.etree.ElementTree as ET
        symbols = {e.get('id') for e in ET.parse(ROOT/'media/graffiti/marks.svg').iter() if e.get('id')}
        fragments = self.page.locator('.street-drawing use').evaluate_all('els=>els.map(e=>e.getAttribute("href").split("#")[1])')
        self.assertTrue(set(fragments).issubset(symbols))
        self.assertTrue({'star-four', 'wordmark', 'comet-head', 'comet-trail'}.issubset(symbols))
        self.assertFalse({'burst-0', 'comet-0'} & symbols)

    def test_18_background_motion_pause_and_preference(self):
        toggle = self.page.locator('#street-motion-toggle')
        expect(toggle).to_be_visible()
        self.page.wait_for_function('getComputedStyle(document.querySelector(".comet-flight")).animationPlayState === "running"')
        toggle.click()
        expect(toggle).to_have_attribute('aria-pressed', 'true')
        self.page.wait_for_function('getComputedStyle(document.querySelector(".comet-flight")).animationPlayState === "paused"')
        before = self.page.locator('.comet-flight').first.evaluate('e=>e.getAnimations()[0].currentTime')
        self.page.wait_for_timeout(150)
        after = self.page.locator('.comet-flight').first.evaluate('e=>e.getAnimations()[0].currentTime')
        self.assertAlmostEqual(before, after, delta=1)
        self.page.reload(wait_until='networkidle')
        expect(toggle).to_have_attribute('aria-pressed', 'true')
        toggle.click()
        expect(toggle).to_have_attribute('aria-pressed', 'false')
        self.page.wait_for_function('getComputedStyle(document.querySelector(".comet-flight")).animationPlayState === "running"')

    def test_19_comets_depart_and_return_without_layout_changes(self):
        self.page.wait_for_function('document.querySelector(".comet-flight").getAnimations().length > 0')
        result = self.page.locator('.comet-flight').first.evaluate('''element => {
            const animation=element.getAnimations()[0];
            const {duration,delay}=animation.effect.getTiming();
            const width=document.documentElement.scrollWidth;
            animation.pause();
            const sample=phase=>{
                animation.currentTime=delay+phase*duration;
                return Number(getComputedStyle(element).opacity);
            };
            return {visible:sample(.25),away:sample(.92),returned:sample(1.25),
                sameWidth:width===document.documentElement.scrollWidth};
        }''')
        self.assertGreater(result['visible'], .8)
        self.assertLess(result['away'], .05)
        self.assertGreater(result['returned'], .8)
        self.assertTrue(result['sameWidth'])

    def test_20_street_reduced_motion_uses_static_drawing(self):
        self.page.emulate_media(reduced_motion='reduce')
        self.page.reload(wait_until='networkidle')
        expect(self.page.locator('#street-motion-toggle')).not_to_be_visible()
        self.assertEqual(self.page.locator('.comet-flight').first.evaluate('e=>getComputedStyle(e).animationName'), 'none')
        self.assertEqual(self.page.locator('.ink-frame').nth(0).evaluate('e=>getComputedStyle(e).opacity'), '1')
        self.assertEqual(self.page.locator('.ink-frame').nth(1).evaluate('e=>getComputedStyle(e).opacity'), '0')
        self.open()
        expect(self.page.locator('#lb-counter')).to_have_text('1 / 17')

    def test_21_pause_still_works_when_storage_is_unavailable(self):
        self.page.add_init_script("Object.defineProperty(window,'localStorage',{get(){throw Error('blocked')}})")
        self.page.reload(wait_until='networkidle')
        self.page.locator('#street-motion-toggle').click()
        expect(self.page.locator('#street-motion-toggle')).to_have_attribute('aria-pressed', 'true')

    def test_22_transparent_artwork_keeps_alpha_in_all_previews(self):
        result = self.page.evaluate("""async () => {
            const result = [];
            for (const width of [480, 960, 1600]) {
                const image = new Image();
                image.src = `media/previews/render13-${width}.webp?v=alpha-1`;
                await image.decode();
                const canvas = document.createElement('canvas');
                canvas.width = canvas.height = width;
                const context = canvas.getContext('2d');
                context.drawImage(image, 0, 0);
                result.push(context.getImageData(0, 0, 1, 1).data[3]);
            }
            return result;
        }""")
        self.assertEqual(result, [0, 0, 0])
        expect(self.page.locator('.gallery-item[data-src="render13.jpg"] img')).to_have_attribute('src', 'media/previews/render13-480.webp?v=alpha-1')

    def test_23_zoom_preserves_focal_point_and_supports_drag_and_wheel(self):
        self.open(12)
        image = self.page.locator('#lb-img')
        fit = image.bounding_box()
        point = (fit['x'] + fit['width'] * .4, fit['y'] + fit['height'] * .45)
        self.page.mouse.dblclick(*point)
        self.page.wait_for_function("width=>Math.abs(document.querySelector('#lb-img').getBoundingClientRect().width-width*2)<2", arg=fit['width'])
        enlarged = image.bounding_box()
        self.assertAlmostEqual(enlarged['x'] + enlarged['width'] * .4, point[0], delta=2)
        self.assertAlmostEqual(enlarged['y'] + enlarged['height'] * .45, point[1], delta=2)
        stage = self.page.locator('#lb-viewport').bounding_box()
        x, y = stage['x'] + stage['width'] / 2, stage['y'] + stage['height'] / 2
        self.page.mouse.move(x, y)
        self.page.mouse.down()
        self.page.mouse.move(x + 70, y + 70, steps=8)
        self.page.mouse.up()
        self.assertGreater(image.bounding_box()['y'], enlarged['y'] + 50)
        self.page.mouse.wheel(0, -200)
        self.page.wait_for_function("width=>document.querySelector('#lb-img').getBoundingClientRect().width>width*2.5", arg=fit['width'])
        self.page.mouse.wheel(0, 10000)
        expect(self.page.locator('#lb-zoom')).to_have_attribute('aria-pressed', 'false')
        self.page.wait_for_function("width=>Math.abs(document.querySelector('#lb-img').getBoundingClientRect().width-width)<2", arg=fit['width'])

    def test_24_delayed_original_cannot_replace_next_render(self):
        held = []
        self.page.route('**/render13.jpg', lambda route: held.append(route))
        self.open(12)
        with self.page.expect_request('**/render13.jpg'):
            self.page.locator('#lb-zoom').click()
        self.page.locator('#lb-next').click()
        expect(self.page.locator('#lb-img')).to_have_attribute('src', 'media/previews/render14-1600.webp')
        self.assertEqual(len(held), 1)
        held[0].fulfill(path=str(ROOT/'render13.jpg'), content_type='image/png')
        self.page.wait_for_load_state('networkidle')
        expect(self.page.locator('#lb-img')).to_have_attribute('src', 'media/previews/render14-1600.webp')
        expect(self.page.locator('#lb-counter')).to_have_text('14 / 17')
        expect(self.page.locator('#lb-zoom')).to_have_attribute('aria-pressed', 'false')

    def test_25_real_touch_pinch_zooms_image_without_changing_render(self):
        context = self.browser.new_context(viewport={'width': 390, 'height': 844}, has_touch=True, is_mobile=True)
        try:
            page = context.new_page()
            page.on('pageerror', lambda error: self.errors.append(str(error)))
            page.goto(self.base, wait_until='networkidle')
            page.locator('.gallery-item[data-src="render13.jpg"]').click()
            page.wait_for_function('document.querySelector("#lb-img").complete && document.querySelector("#lb-img").naturalWidth>0')
            box = page.locator('#lb-viewport').bounding_box()
            cx, cy = box['x'] + box['width'] / 2, box['y'] + box['height'] / 2
            session = context.new_cdp_session(page)
            def fingers(distance):
                return [{'x': cx-distance, 'y': cy, 'id': 1}, {'x': cx+distance, 'y': cy, 'id': 2}]
            session.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': fingers(40)})
            for distance in [50, 60, 70, 80]:
                session.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': fingers(distance)})
            session.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
            expect(page.locator('#lb-zoom')).to_have_attribute('aria-pressed', 'true')
            expect(page.locator('#lb-counter')).to_have_text('13 / 17')
            session.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': fingers(80)})
            for distance in [70, 60, 50, 40]:
                session.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': fingers(distance)})
            session.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
            expect(page.locator('#lb-zoom')).to_have_attribute('aria-pressed', 'false')
            expect(page.locator('#lb-caption')).to_have_text('Вкусный малышочек')
        finally:
            context.close()

    def test_26_language_switch_translates_page_and_persists(self):
        toggle = self.page.locator('#language-toggle')
        expect(toggle).to_have_accessible_name('Switch to English')
        toggle.click()
        expect(self.page.locator('html')).to_have_attribute('lang', 'en')
        expect(self.page.locator('.hero h1')).to_have_text("Hey,I'm CriSpy!")
        expect(self.page.locator('#contact')).to_have_text('Contact me')
        expect(self.page.locator('.service-name').first).to_have_text('Head render (no extra models)')
        expect(self.page.locator('.review-quote').nth(1)).to_have_text('Exactly what I wanted, 8/10 — nothing to add.')
        self.assertNotRegex(self.page.locator('body').inner_text(), '[А-Яа-яЁё]')
        self.assertTrue(self.page.locator('meta[name="description"]').get_attribute('content').startswith('CriSpy — Minecraft renders'))
        self.page.reload(wait_until='networkidle')
        expect(self.page.locator('html')).to_have_attribute('lang', 'en')
        expect(toggle).to_have_accessible_name('Переключить на русский')
        toggle.click()
        expect(self.page.locator('html')).to_have_attribute('lang', 'ru')
        expect(self.page.locator('.hero h1')).to_have_text('Привет,Я Криспи!')
        self.page.reload(wait_until='networkidle')
        expect(self.page.locator('html')).to_have_attribute('lang', 'ru')

    def test_27_english_viewer_labels_order_message_and_live_state(self):
        self.page.locator('#language-toggle').click()
        self.filter('head-basic', 2)
        self.open()
        expect(self.page.locator('#lb-caption')).to_have_text('Guy with Glasses')
        expect(self.page.locator('#lb-category')).to_have_text('Head without models')
        expect(self.page.locator('.lightbox-thumb').first).to_have_accessible_name('Show: Guy with Glasses')
        self.page.locator('#lb-next').click()
        expect(self.page.locator('#lb-caption')).to_have_text('Honey Head')
        expect(self.page.locator('#lb-counter')).to_have_text('2 / 2')
        message = parse_qs(urlparse(self.page.locator('#lb-order').get_attribute('href')).query)['text'][0]
        self.assertEqual(message, 'Hi! I’d like to discuss a render in the style of “Honey Head”.')
        self.page.locator('#lb-zoom').click()
        expect(self.page.locator('#lb-zoom')).to_have_accessible_name('Fit image to view')
        expect(self.page.locator('#lb-zoom .tool-label')).to_have_text('Fit to view')
        # Translating an already open viewer must not reset its zoom or selection.
        self.page.locator('#language-toggle').evaluate('element=>element.click()')
        expect(self.page.locator('#lb-caption')).to_have_text('Медовая голова')
        expect(self.page.locator('#lb-counter')).to_have_text('2 / 2')
        expect(self.page.locator('#lb-zoom')).to_have_attribute('aria-pressed', 'true')
        expect(self.page.locator('#lb-zoom')).to_have_accessible_name('Уместить изображение')
        self.page.keyboard.press('Escape')
        expect(self.page.locator('[data-filter="head-basic"]')).to_have_attribute('aria-pressed', 'true')

    def test_28_english_viewer_error_and_motion_states_are_translated(self):
        self.page.locator('#language-toggle').click()
        toggle = self.page.locator('#street-motion-toggle')
        toggle.click()
        expect(toggle).to_have_accessible_name('Resume background animation')
        expect(toggle.locator('span')).to_have_text('Resume background')
        self.page.route('**/render1-1600.webp', lambda route: route.abort())
        self.page.locator('.gallery-item').first.click()
        expect(self.page.locator('#lb-feedback')).to_contain_text('Could not load the image.')
        expect(self.page.locator('#lb-feedback a')).to_have_text('Open original')
        self.page.keyboard.press('ArrowRight')
        expect(self.page.locator('#lb-caption')).to_have_text('Halloween')
        self.page.wait_for_function('document.querySelector("#lb-img").complete && document.querySelector("#lb-img").naturalWidth>0')
        expect(self.page.locator('#lb-feedback')).not_to_be_visible()

    def test_29_language_control_fits_mobile_and_keeps_menu_state(self):
        self.page.locator('#language-toggle').click()
        for width in [320, 360, 390, 640, 900, 902, 1024, 1440]:
            self.page.set_viewport_size({'width': width, 'height': 844})
            brand = self.page.locator('.graffiti-brand').bounding_box()
            toggle = self.page.locator('#language-toggle').bounding_box()
            self.assertLessEqual(brand['x'] + brand['width'], toggle['x'])
            self.assertLessEqual(toggle['x'] + toggle['width'], width)
            self.assertFalse(self.page.evaluate('document.documentElement.scrollWidth>innerWidth'), width)
            if width <= 900:
                burger = self.page.locator('#burger').bounding_box()
                self.assertLessEqual(toggle['x'] + toggle['width'], burger['x'])
        self.page.set_viewport_size({'width': 320, 'height': 568})
        self.page.locator('#burger').click()
        expect(self.page.locator('#burger')).to_have_accessible_name('Close menu')
        expect(self.page.locator('#mobile-nav a[href="#services"]')).to_have_text('Services')
        self.page.locator('#language-toggle').click()
        expect(self.page.locator('#burger')).to_have_attribute('aria-expanded', 'true')
        expect(self.page.locator('#burger')).to_have_accessible_name('Закрыть меню')
        expect(self.page.locator('#mobile-nav a[href="#services"]')).to_have_text('Услуги')
        self.page.locator('#mobile-nav a[href="#services"]').click()
        expect(self.page.locator('#burger')).to_have_attribute('aria-expanded', 'false')

    def test_30_language_switch_works_without_preference_storage(self):
        self.page.add_init_script("Object.defineProperty(window,'localStorage',{get(){throw Error('blocked')}})")
        self.page.reload(wait_until='networkidle')
        self.page.locator('#language-toggle').click()
        expect(self.page.locator('html')).to_have_attribute('lang', 'en')
        expect(self.page.locator('.hero h1')).to_have_text("Hey,I'm CriSpy!")
        self.page.locator('#language-toggle').click()
        expect(self.page.locator('html')).to_have_attribute('lang', 'ru')


if __name__ == '__main__':
    unittest.main(verbosity=2)
