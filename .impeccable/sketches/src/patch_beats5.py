import sys, pathlib

S = pathlib.Path(sys.argv[1])
t = (S / "story_template.bak3.html").read_text(encoding="utf-8")


def rep(a, b):
    global t
    assert t.count(a) == 1, f"COUNT {t.count(a)}: " + a[:100]
    t = t.replace(a, b)


# engine
a = t.index("// ---------- story ----------")
b = t.index("// ---------- pixel map ----------")
t = t[:a] + (S / "story_engine7.js").read_text(encoding="utf-8") + "\n" + t[b:]

# picnic: blanket photo plus item cut-outs, composed on the canvas
a = t.index('<img id="scene"')
b = t.index(">", a) + 1
t = t[:a] + ('<img id="scene" src="scene/web/blanket.jpg" alt="" hidden><img id="items" src="scene/web/picnic_items.png" alt="" hidden>'
             '<p class="sr-only">A picnic laid out on a checked blanket, made entirely of disposable plastics: cups, plates, cutlery, straws, a soda bottle, squeeze bottles, wrapped sandwiches, a food tub, a beach ball and a jump rope.</p>') + t[b:]

# captions
a = t.index('<div class="cap c0')
b = t.index('<div class="cue"')
caps = '''<div class="cap c0 dk" data-a=".45" data-b="1.45"><h1>Plastic is everywhere&hellip;</h1></div>
<div class="cap c1 dk" data-a="4.0" data-b="5.4"><h2>Microplastics were first described in the ocean more than 50&nbsp;years ago.</h2><p class="src">Carpenter et al. (1972), &ldquo;Polystyrene spherules in coastal waters,&rdquo; Science 178:749. doi:10.1126/science.178.4062.749</p></div>
<div class="cap c1n dk" data-a="5.4" data-b="7.2"><h2>Now picture every particle as a published study. Thousands more arrive every year.</h2></div>
<div class="cap c2 dk" data-a="8.5" data-b="10.5"><h2>Connected, studies become knowledge.</h2></div>
<div class="cap c2b bot dk" data-a="9.2" data-b="10.5"><p>Grouped by what they study and linked by who did the work, scattered results start to form a picture.</p></div>
<div class="cap cb dk" data-a="11.6" data-b="12.9"><h2>Put to work, knowledge becomes understanding.</h2></div>
<div class="cap c3s" data-a="17.45" data-b="20.55"><p class="src">Plastics-pollution research works per year, worldwide. OpenAlex, query __QV__, fetched __FETCHED__. One dot = <span id="unit"></span> works.</p></div>
<div class="cap c3" data-a="19.2" data-b="20.55"><h2>Plastic pollution research is expanding at an unprecedented pace.</h2><p>The world needs innovative tools to turn data into knowledge and solutions to effectively react to this global crisis.</p></div>
<div class="cap c5" data-a="21.8" data-b="23.4"><h2>See where the evidence is, worldwide, and where it is missing.</h2><p data-a="22.3">A live evidence map sorts every study by what it examines and where.</p></div>
<div class="cap c4" data-a="24.6" data-b="26.1"><h2>See who works with whom, and forge new connections.</h2><p data-a="25.1">Collaboration networks show the research communities and the people who bridge them.</p><p class="src" data-a="25.1">Illustrative network layout.</p></div>
<div class="cap c6" data-a="27.3" data-b="28.5"><h2>The problem is global.</h2><p data-a="27.75">Plastics research now comes from almost every country.</p><p class="src" data-a="27.75">Illustrative shading until the global country counts are built.</p></div>
<div class="cap c7" data-a="29.6" data-b="99"><h2>Local knowledge and connections matter.</h2><p data-a="30">Regional atlases zoom in on the people, monitoring, funding and policy of one place. Powered by local experts and community leaders.</p><p class="cta" data-a="30.35"><a class="btn solid" href="#ambassadors">Join the movement, and become a local ambassador <svg width="14" height="10" viewBox="0 0 14 10" aria-hidden="true"><path d="M1 5h11M8 1l4 4-4 4" fill="none" stroke="currentColor" stroke-width="1.6"/></svg></a></p><p class="sep" data-a="30.7">California is live; Norway is next.</p></div>
'''
t = t[:a] + caps + t[b:]

# styles
rep("#story{position:relative;height:1650vh}", "#story{position:relative;height:3080vh}")
rep(".c1,.c2,.cb,.c4,.c5,.c7{max-width:min(36vw,560px)}",
    ".c1,.c1n,.c2,.cb,.c4,.c5,.c7,.c2b{max-width:min(36vw,560px)}\n"
    ".sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap}\n"
    ".c0{top:calc(60px + 4vh)!important;max-width:none}\n"
    ".cap.bot{top:auto;bottom:calc(7vh + 24px)} .bot p{margin:0;font-size:clamp(19px,1.8vw,27px);line-height:1.3;letter-spacing:-.01em;color:#eef1f8}\n"
    ".c3{top:calc(60px + 17vh)!important;max-width:none} .c3 h2{font-size:clamp(26px,2.8vw,42px);max-width:min(46vw,720px)} .c3 p{margin-top:12px;font-size:clamp(15px,1.2vw,18px);max-width:none;white-space:nowrap}\n"
    ".c3s{max-width:none} .c3s .src{margin-top:0;max-width:none;white-space:nowrap}\n"
    ".c7 .cta{margin-top:22px} .c7 .cta .btn{font-size:16px;padding:11px 18px;white-space:normal;text-align:left;text-decoration:none}\n"
    ".c7 .sep{margin-top:1.3em;font-size:clamp(19px,1.6vw,24px);color:var(--ink);letter-spacing:-.01em}\n"
    "#stage [data-a]:not(.cap){opacity:0}")
rep("@media (max-width:860px){.c0{max-width:none}",
    "@media (max-width:860px){.c0{max-width:none} .c1,.c1n,.c2,.cb,.c4,.c5,.c7,.c2b{max-width:none} "
    ".c3{top:auto!important;bottom:5vh} .c3 h2{max-width:none} .c3 p,.c3s .src{white-space:normal} .c3s{max-width:calc(100vw - 2*var(--gut))}")
rep("#stack img{position:absolute;left:0;top:0;transform-origin:50% 50%;opacity:0;box-shadow:0 10px 30px rgba(0,0,0,.55);background:#fff}",
    "#stack img{position:absolute;left:0;top:0;transform-origin:50% 50%;opacity:0;box-shadow:0 10px 30px rgba(0,0,0,.55);background:#fff}")

a = t.index('<div class="pcred">')
b = t.index("</div>", a) + 6
body = t[a + len('<div class="pcred">'):b - 6]
body = body.replace("<b>Paper first pages</b> reproduced under CC BY 4.0 (CC BY), with download stamps removed: ", "")
body = body.replace("10.1021/acs.est.6c01796 (doi:10.1021/acs.est.6c01796)", "Lost in a Sea of Information: The Microplastics Publication Deluge (doi:10.1021/acs.est.6c01796)")
t = t[:a] + '<details class="pcred"><summary>Image credits</summary><p>Paper first pages reproduced under CC BY 4.0, with download stamps removed: ' + body + '</p></details>' + t[b:]
rep("footer b{color:var(--ink);font-weight:600} .pcred{flex-basis:100%;font-size:12px}",
    "footer b{color:#fff;font-weight:600} .pcred{flex-basis:100%;font-size:11px;line-height:1.5;color:#9fb0bf} .pcred summary{cursor:pointer;font-size:12px;width:max-content;color:var(--night2)} .pcred p{margin-top:8px;max-width:150ch}")

# ---- brand theme from the Plastiverse Live logo ----
rep("--match:#e5386d;", "--match:#FA6B68;--coral-ink:#D9443F;--sun:#FFF49A;--gold:#E2B714;")
rep("--night:#0a0a0b;", "--night:#000000;")
rep("--night2:#9aa6c2;", "--night2:#C5EADF;")
for a_, b_ in [("#17203a","#17263D"),("#4f5a74","#4d5d73"),("#c3cdd6","#c4d0d6"),("#1a9c96","#436487"),("#7dcdc6","#86a9bf"),("#cfe9e6","#C5EADF"),("#e6ecef","#e9f1ef"),("#e7f2f1","#eef4f2"),("#e5386d","#FA6B68"),("rgba(23,32,58","rgba(23,38,61")]:
    t = t.replace(a_, b_)
rep(":focus-visible{outline:2px solid var(--match);", ":focus-visible{outline:2px solid var(--coral-ink);")
rep(".go{font-size:14px;font-weight:600;color:var(--match);", ".go{font-size:14px;font-weight:600;color:var(--coral-ink);")
rep("font-weight:600;color:var(--match);text-decoration:none;white-space:nowrap}", "font-weight:600;color:var(--coral-ink);text-decoration:none;white-space:nowrap}")
a = t.index('<a class="brand" href="#">'); b = t.index("</a>", a) + 4
t = t[:a] + '<a class="brand" href="#" aria-label="Plastiverse Live home"><svg class="mk" width="26" height="26" viewBox="0 0 26 26" aria-hidden="true"><circle cx="13" cy="13" r="5"/><g><line x1="20.60" y1="13.00" x2="23.40" y2="13.00"/><line x1="20.02" y1="15.91" x2="23.72" y2="17.44"/><line x1="18.37" y1="18.37" x2="20.35" y2="20.35"/><line x1="15.91" y1="20.02" x2="17.44" y2="23.72"/><line x1="13.00" y1="20.60" x2="13.00" y2="23.40"/><line x1="10.09" y1="20.02" x2="8.56" y2="23.72"/><line x1="7.63" y1="18.37" x2="5.65" y2="20.35"/><line x1="5.98" y1="15.91" x2="2.28" y2="17.44"/><line x1="5.40" y1="13.00" x2="2.60" y2="13.00"/><line x1="5.98" y1="10.09" x2="2.28" y2="8.56"/><line x1="7.63" y1="7.63" x2="5.65" y2="5.65"/><line x1="10.09" y1="5.98" x2="8.56" y2="2.28"/><line x1="13.00" y1="5.40" x2="13.00" y2="2.60"/><line x1="15.91" y1="5.98" x2="17.44" y2="2.28"/><line x1="18.37" y1="7.63" x2="20.35" y2="5.65"/><line x1="20.02" y1="10.09" x2="23.72" y2="8.56"/></g></svg><span class="wm">PLASTIVERSE <b>LIVE</b></span></a>' + t[b:]
rep('<footer id="updates">', '<footer id="updates"><img class="flogo" src="brand/logo_564.png" width="282" height="247" alt="Plastiverse Live logo: scattered plastic fragments flow into a bright node and a network of research">')
rep(".brand,.btn{white-space:nowrap}", ".brand,.btn{white-space:nowrap} "
    ".mk circle{fill:var(--gold)} .mk line{stroke:var(--gold);stroke-width:1.4;stroke-linecap:round} header.top.on-dark .mk circle{fill:var(--sun)} header.top.on-dark .mk line{stroke:var(--sun)} "
    ".wm{font-weight:700;letter-spacing:.09em;font-size:18px} .wm b{font-weight:700;color:var(--coral-ink)} header.top.on-dark .wm b{color:var(--match)} "
    "footer{background:#000;color:var(--night2);border-top:0;align-items:flex-start} footer a{color:#fff} .stage.lit .skip,.stage.lit .cue{color:var(--ink2)} .flogo{width:min(282px,60vw);height:auto;flex-basis:100%;max-width:282px}")
(S / "story_template.html").write_text(t, encoding="utf-8")
print("ok")
