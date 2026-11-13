"""The owner's acceptance walk on a real WordPress site, in a real browser engine. Prints what it finds.

Run after the theme, plugin, content and posts are installed:
  python tests/wordpress/walkthrough.py http://localhost:8089 <screenshot folder> <theme slug>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from wp_browser import Browser

PAGES = {"home": "/", "about": "/about/", "services": "/services/", "projects": "/projects/", "contact": "/contact/"}
WIDTHS = {"desktop": 1440, "tablet": 820, "mobile": 390}
results: list[tuple[bool, str]] = []


def check(ok: bool, text: str) -> None:
    results.append((bool(ok), text))
    print(("PASS " if ok else "FAIL ") + text, flush=True)


def full_shot(browser: Browser, path: Path, width: int, url: str) -> dict:
    browser.view.resize(width, 1000)
    browser.wait(150)
    browser.open(url, 700)
    # Scrolled through as a visitor would, so that lazy images load. An image that has not loaded counts as broken.
    height = int(browser.js("document.documentElement.scrollHeight"))
    for y in range(0, height, 500):
        browser.js(f"scrollTo(0,{y});true")
        browser.wait(120)
    browser.js("scrollTo(0,0);true")
    browser.wait(400)
    facts = json.loads(browser.js("JSON.stringify({inner:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth,h:document.documentElement.scrollHeight,brokenImages:[...document.images].filter(i=>i.offsetParent&&!(i.complete&&i.naturalWidth)).map(i=>i.src)})"))
    # Squeezed columns do not overflow, so they are measured directly.
    facts["narrow"] = json.loads(browser.js("JSON.stringify([...document.querySelectorAll('.wp-block-column')].map(c=>Math.round(c.getBoundingClientRect().width)).filter(w=>w>0&&w<140))"))
    browser.view.resize(width, min(int(facts["h"]), 7000))
    browser.wait(1500)  # The engine paints a resized page in stages.
    browser.view.grab().save(str(path))
    browser.view.resize(width, 1000)
    return facts


def visitor(base: str, out: Path) -> None:
    browser = Browser(base)
    for name, url in {**PAGES, "single": "/sample-project-harbour-booking-system/", "archive": "/category/projects/", "not-found": "/no-such-page/"}.items():
        for device, width in WIDTHS.items():
            facts = full_shot(browser, out / f"{name}-{device}.png", width, url)
            check(facts["scroll"] <= facts["inner"], f"{name} at {width}: no sideways scrolling ({facts['scroll']} in {facts['inner']})")
            check(not facts["narrow"], f"{name} at {width}: no squeezed columns {facts['narrow'][:4] or ''}")
            check(not facts["brokenImages"], f"{name} at {width}: all images load {facts['brokenImages'][:2] or ''}")

    # Navigation, as a visitor clicks it.
    browser.view.resize(1440, 1000)
    browser.open("/")
    links = json.loads(browser.js("JSON.stringify([...document.querySelectorAll('.mts-wp-nav a')].map(a=>[a.textContent.trim(),a.href]))"))
    check([label for label, _ in links] == ["Home", "About", "Services", "Projects", "Contact"], f"menu shows the five pages: {[l for l, _ in links]}")
    for label, href in links:
        browser.open(href, 200)
        heading = browser.js("(document.querySelector('main h1')||{}).textContent||''")
        current = browser.js("(document.querySelector('.mts-wp-nav a[aria-current=page]')||{}).textContent||''")
        check(bool(heading), f"menu link {label} opens a page headed '{heading[:40]}'")
        check(current.strip() == label, f"menu marks {label} as current ('{current.strip()}')")
    # Footer shared.
    browser.open("/about/")
    footer_about = browser.js("document.querySelector('.mts-footer, footer').textContent.trim().slice(0,60)")
    browser.open("/contact/")
    check(footer_about == browser.js("document.querySelector('.mts-footer, footer').textContent.trim().slice(0,60)"), "footer is the same on different pages")

    # Mobile menu.
    browser.view.resize(390, 800)
    browser.open("/", 600)
    shown = browser.js("getComputedStyle(document.querySelector('.wp-block-navigation__responsive-container-open')).display")
    check(shown != "none", f"mobile: menu button is visible ({shown})")
    closed = browser.js("!document.querySelector('.mts-wp-nav .wp-block-navigation__responsive-container').classList.contains('is-menu-open')")
    check(closed, "mobile: menu starts closed")
    browser.js("document.querySelector('.wp-block-navigation__responsive-container-open').click();true")
    browser.wait(500)
    check(browser.js("document.querySelector('.mts-wp-nav .wp-block-navigation__responsive-container').classList.contains('is-menu-open')"), "mobile: menu opens when pressed")
    browser.view.grab().save(str(out / "mobile-menu-open.png"))
    target = browser.js("(()=>{const a=[...document.querySelectorAll('.mts-wp-nav .is-menu-open a')].find(a=>a.textContent.trim()==='Services');const r=a.getBoundingClientRect();return r.width>0&&r.height>0?a.href:''})()")
    check(target.endswith("/services/"), f"mobile: Services is visible in the open menu ({target})")

    # What the owner set per device reaches the real site, and is not a scaled desktop.
    sizes = {}
    for device, width in WIDTHS.items():
        browser.view.resize(width, 1000)
        browser.open("/", 500)
        sizes[device] = browser.js("JSON.stringify((()=>{const h=document.querySelector('main h1');const c=getComputedStyle(h);const img=[...document.images].find(i=>i.src.includes('about'));return {size:parseFloat(c.fontSize),align:c.textAlign,about:img?getComputedStyle(img.closest('figure')||img).display:'absent',columns:getComputedStyle(document.querySelector('.mts-query .wp-block-post-template')).gridTemplateColumns.split(' ').length}})())")
        sizes[device] = json.loads(sizes[device])
    print("device facts:", sizes)
    root = 16
    check(sizes["tablet"]["size"] == 3 * root and sizes["mobile"]["size"] == 2.25 * root and sizes["desktop"]["size"] > sizes["tablet"]["size"], f"heading sizes follow each device: {[sizes[d]['size'] for d in WIDTHS]}")
    check(sizes["mobile"]["align"] == "center" and sizes["desktop"]["align"] != "center", "the mobile alignment stays on mobile")
    check(sizes["mobile"]["about"] == "none" and sizes["tablet"]["about"] != "none" and sizes["desktop"]["about"] != "none", "the image hidden on mobile is hidden only on mobile")
    check(sizes["desktop"]["columns"] == 3 and sizes["mobile"]["columns"] == 1, f"posts grid columns respond: {[sizes[d]['columns'] for d in WIDTHS]}")

    # Live posts.
    browser.view.resize(1440, 1000)
    browser.open("/")
    titles = json.loads(browser.js("JSON.stringify([...document.querySelectorAll('.wp-block-post-title')].map(a=>a.textContent.trim()))"))
    check(titles == ["Sample project: clinic scheduling", "Sample project: farm records app", "Sample project: harbour booking system"], f"homepage lists the 3 newest posts in its category, not the news post: {titles}")
    check(browser.js("[...document.querySelectorAll('.wp-block-post-featured-image img')].length") == 3, "homepage shows real featured images")
    check(browser.js("document.querySelectorAll('main .wp-block-post .wp-block-post-author-name').length") == 0, "the hidden author detail stays hidden")
    href = browser.js("document.querySelector('.wp-block-post-title a').href")
    browser.open(href)
    check(browser.js("document.querySelector('main h1').textContent.trim()") == titles[0], "a post opens with its title, through the single template")
    check("invented test content" in browser.js("document.querySelector('.wp-block-post-content').textContent"), "the single template shows the post's body")
    check(browser.js("!!document.querySelector('.mts-header')&&!!document.querySelector('footer')"), "single post has the shared header and footer")
    browser.open("/projects/")
    listed = json.loads(browser.js("JSON.stringify([...document.querySelectorAll('.wp-block-post-title')].map(a=>a.textContent.trim()))"))
    check(len(listed) == 3 and not any("news" in t for t in listed), f"the Projects page filters by category: {listed}")
    browser.open("/category/news/")
    titles = json.loads(browser.js("JSON.stringify([...document.querySelectorAll('.wp-block-post-title')].map(a=>a.textContent.trim()))"))
    check(titles == ["Sample news: office update"], f"archive follows the category opened: {titles}")
    browser.open("/no-such-page/")
    check(browser.js("!!document.querySelector('.mts-header')") and browser.js("document.body.classList.contains('error404')"), "unknown addresses use the 404 template")


def editor(base: str, out: Path, slug: str) -> None:
    browser = Browser(base)
    browser.login()
    browser.open("/wp-admin/edit.php?post_type=page")
    author = browser.js("document.querySelector('#the-list tr .column-author').textContent.trim()")
    check(author == "admin", f"imported pages have an author ({author})")
    ids = json.loads(browser.js("JSON.stringify(Object.fromEntries([...document.querySelectorAll('#the-list tr')].map(r=>[r.querySelector('.row-title').textContent.trim(),+r.id.replace('post-','')])))"))
    total_invalid = 0
    for title in ("Home", "About", "Services", "Projects", "Contact"):
        ready = browser.open_editor(ids[title])
        browser.wait(1500)
        count, bad = browser.invalid_in_editor() if ready else (0, [{"name": "editor not ready"}])
        total_invalid += len(bad)
        check(ready and not bad and count > 3, f"Gutenberg opens {title}: {count} blocks, {len(bad)} invalid {[b['name'] for b in bad][:3]}")
    browser.open_editor(ids["Home"])
    browser.wait(1500)
    for pattern in browser.patterns():
        if pattern["name"].startswith(f"{slug}/"):
            count, bad = browser.parse_report(pattern["content"])
            total_invalid += len(bad)
            check(not bad, f"Gutenberg parses {pattern['name']}: {count} blocks, {len(bad)} invalid")
    control = browser.parse_report('<!-- wp:heading {"level":2} -->\n<h3 class="wp-block-heading">x</h3>\n<!-- /wp:heading -->')[1]
    check(bool(control), "control: a deliberately broken block is reported, so this check can fail")

    # Edit in Gutenberg, as a person would: change a heading, add a paragraph, save.
    browser.js("wp.data.dispatch('core/preferences').set('core/edit-post','welcomeGuide',false);wp.data.dispatch('core/preferences').set('core/edit-site','welcomeGuide',false);true")
    browser.wait(500)
    names = json.loads(browser.js("JSON.stringify((()=>{const s=new Set();const w=l=>l.forEach(x=>{s.add(x.name);w(x.innerBlocks)});w(wp.data.select('core/block-editor').getBlocks());return [...s]})())"))
    check("core/query" in names and "core/heading" in names, f"the homepage's posts section is a real Query Loop in the editor: {sorted(names)}")
    browser.view.grab().save(str(out / "gutenberg-home.png"))
    done = browser.js("""
      (()=>{const be=wp.data.select('core/block-editor');const find=(l,n)=>{for(const b of l){if(b.name===n)return b;const f=find(b.innerBlocks,n);if(f)return f}};
       const h=find(be.getBlocks(),'core/heading');wp.data.dispatch('core/block-editor').updateBlockAttributes(h.clientId,{content:'Edited in Gutenberg'});
       const top=be.getBlocks()[0];wp.data.dispatch('core/block-editor').insertBlock(wp.blocks.createBlock('core/paragraph',{content:'A paragraph added in Gutenberg.'}),0,h?be.getBlockRootClientId(h.clientId):undefined);
       window.__saved=false;wp.data.dispatch('core/editor').savePost().then(()=>{window.__saved=true});return true})()""")
    saved = browser.until("window.__saved===true", 30)
    check(bool(done and saved), "Gutenberg saves the edited homepage")
    browser.open(f"{base}/?nocache=1", 500)
    text = browser.js("document.querySelector('main').textContent")
    check("Edited in Gutenberg" in text and "A paragraph added in Gutenberg." in text, "the edits appear on the live homepage")
    check(browser.js("document.querySelectorAll('main .wp-block-post-title').length") == 3, "the live posts still work after editing")
    browser.view.resize(1440, 1000)
    browser.view.grab().save(str(out / "home-after-gutenberg-edit.png"))
    browser.open_editor(ids["Home"])
    browser.wait(1500)
    count, bad = browser.invalid_in_editor()
    check(not bad, f"reopened after saving: {count} blocks, {len(bad)} invalid")

    # Shared parts in the site editor.
    browser.open(f"/wp-admin/site-editor.php?p=%2Fwp_template_part%2F{slug}%2F%2Fheader&canvas=edit", 500)
    ready = browser.until("!!(window.wp&&wp.data&&wp.data.select('core/block-editor')&&wp.data.select('core/block-editor').getBlocks().length)", 40)
    browser.wait(2500)
    browser.js("window.__names=(()=>{const s=new Set();const w=l=>l.forEach(x=>{s.add(x.name);w(wp.data.select('core/block-editor').getBlocks(x.clientId));w(x.innerBlocks)});w(wp.data.select('core/block-editor').getBlocks());return [...s]})();true")
    part = json.loads(browser.js("JSON.stringify(window.__names||[])"))
    browser.view.grab().save(str(out / "site-editor-header.png"))
    check(ready and bool(part), f"the site editor opens the shared header: {sorted(part)}")

    # The import screen, pressed again: nothing should change.
    browser.open("/wp-admin/tools.php?page=" + slug + "-content")
    browser.view.grab().save(str(out / "import-screen.png"))
    check(browser.js("!!document.querySelector('form input[type=submit]')"), "the import screen is there")
    browser.js("document.querySelector('.wrap form input[type=submit]').click();true")
    browser.wait(3000)
    states = json.loads(browser.js("JSON.stringify([...document.querySelectorAll('table.widefat tbody tr')].map(r=>r.lastElementChild.textContent))"))
    check(states == ["kept"] * 5, f"pressing import again keeps every page: {states}")
    browser.open(base + "/", 300)
    check("Edited in Gutenberg" in browser.js("document.querySelector('main').textContent"), "the owner's Gutenberg edit survived the second import")
    print("TOTAL INVALID BLOCKS:", total_invalid)


if __name__ == "__main__":
    base, out, slug = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
    out.mkdir(parents=True, exist_ok=True)
    visitor(base, out)
    editor(base, out, slug)
    failed = [t for ok, t in results if not ok]
    print(f"\n{len(results) - len(failed)} passed, {len(failed)} failed")
    for text in failed:
        print("FAILED:", text)
    raise SystemExit(1 if failed else 0)
