import asyncio, sys
from playwright.async_api import async_playwright
from PIL import Image, ImageDraw

url, outdir, vw, vh = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
TOT = 28.6
UNITS = [float(x) for x in sys.argv[5].split(",")]


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="msedge")
        pg = await b.new_page(viewport={"width": vw, "height": vh})
        errs = []
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.goto(url)
        await pg.add_style_tag(content="html{scroll-behavior:auto!important}")
        await pg.wait_for_timeout(700)
        await pg.screenshot(path=f"{outdir}/intro_mid.png")
        await pg.wait_for_timeout(2000)
        H = await pg.evaluate("document.getElementById('story').offsetHeight - innerHeight")
        shots = []
        for u in UNITS:
            await pg.evaluate(f"window.scrollTo(0,{int(H * u / TOT)})")
            await pg.wait_for_timeout(650)
            fn = f"{outdir}/u{u:05.2f}.png"
            await pg.screenshot(path=fn)
            shots.append((u, fn))
        print("errors:", errs[:5])
        await b.close()
    cols = 4
    tw = 480
    th = int(tw * vh / vw)
    rows = (len(shots) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * (th + 18)), "white")
    d = ImageDraw.Draw(sheet)
    for k, (u, fn) in enumerate(shots):
        im = Image.open(fn).convert("RGB").resize((tw, th))
        x, y = (k % cols) * tw, (k // cols) * (th + 18)
        sheet.paste(im, (x, y + 18))
        d.text((x + 4, y + 3), f"u={u}", fill="black")
    sheet.save(f"{outdir}/sheet.png")


asyncio.run(main())
