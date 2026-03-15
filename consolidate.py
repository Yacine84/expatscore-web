import os
import re
import shutil

ROOT_DIR = "."

def cleanup():
    # Remove redundant files not needed for production per user instructions
    redundant_files = ['agent.py', 'generate_pages.py', 'data.csv', 'consolidate.py']
    redundant_dirs = ['templates', 'wenn-du-dauerhaft-ins-minus-rutschst-und-rückzahlungen-ausbleiben-wer-sein-konto-sauber-führt']
    
    for d in redundant_dirs:
        if os.path.exists(d):
            shutil.rmtree(d)
            print(f"Removed redundant dir {d}")
            
    for root, dirs, files in os.walk(ROOT_DIR):
        for file in files:
            if file == ".DS_Store":
                os.remove(os.path.join(root, file))

    for f in redundant_files:
        if os.path.exists(f) and f != 'consolidate.py':
            os.remove(f)
            print(f"Removed redundant file {f}")

def standardize_assets():
    os.makedirs("assets/css", exist_ok=True)
    os.makedirs("assets/js", exist_ok=True)
    
    if os.path.exists("style.css"):
        shutil.move("style.css", "assets/css/style.css")
        print("Moved style.css into /assets/css/")
        
    if os.path.exists("script.js"):
        shutil.move("script.js", "assets/js/script.js")
        print("Moved script.js into /assets/js/")

def unify_ui_and_fix_paths():
    with open("index.html", "r", encoding="utf-8") as f:
        master = f.read()
        
    # Isolate Header and Footer blocks
    header_regex = r'(<!--\s*GLOBAL HEADER.*?-->\s*<header class="global-header">.*?</header>)'
    footer_regex = r'(<!--\s*FOOTER.*?-->\s*<footer class="global-footer">.*?</footer>)'
    
    hm = re.search(header_regex, master, re.DOTALL)
    fm = re.search(footer_regex, master, re.DOTALL)
    
    if not hm or not fm:
        hm = re.search(r'(<header class="global-header">.*?</header>)', master, re.DOTALL)
        fm = re.search(r'(<footer class="global-footer">.*?</footer>)', master, re.DOTALL)
        
    master_header = hm.group(1)
    master_footer = fm.group(1)
    
    html_files = []
    for root, dirs, files in os.walk(ROOT_DIR):
        if ".git" in root or "node_modules" in root or "assets" in root:
            continue
        for f in files:
            if f.endswith(".html"):
                html_files.append(os.path.join(root, f))
                
    for path in html_files:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            
        rel_path = os.path.relpath(path, ROOT_DIR)
        parts = rel_path.split(os.sep)
        depth = len(parts) - 1
        prefix = "../" * depth if depth > 0 else ""
        
        # Modify href and src links within the master block depending on the depth 
        def fix_links(block):
            def replacer(m):
                attr, url = m.group(1), m.group(2)
                # Avoid modifying external URLs, mailto, tel, fragments, or empty
                if url.startswith("http") or url.startswith("mailto") or url.startswith("tel") or url.startswith("#") or not url:
                    return m.group(0)
                return f'{attr}="{prefix}{url}"'
            return re.sub(r'(href|src)="([^"]*)"', replacer, block)
            
        loc_header = fix_links(master_header)
        loc_footer = fix_links(master_footer)
        
        # Unify header
        if re.search(header_regex, content, flags=re.DOTALL):
            content = re.sub(header_regex, lambda _: loc_header, content, flags=re.DOTALL)
        else:
            content = re.sub(r'<header class="global-header">.*?</header>', lambda _: loc_header, content, flags=re.DOTALL)
            
        # Unify footer
        if re.search(footer_regex, content, flags=re.DOTALL):
            content = re.sub(footer_regex, lambda _: loc_footer, content, flags=re.DOTALL)
        else:
            content = re.sub(r'<footer class="global-footer">.*?</footer>', lambda _: loc_footer, content, flags=re.DOTALL)
            
        # Standardize asset paths within the entire document
        content = re.sub(r'href="(?:\.\./)*style\.css"', f'href="{prefix}assets/css/style.css"', content)
        content = re.sub(r'src="(?:\.\./)*script\.js"', f'src="{prefix}assets/js/script.js"', content)
        
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Unified and path-fixed: {path}")

if __name__ == "__main__":
    standardize_assets()
    unify_ui_and_fix_paths()
    cleanup()
    print("Consolidation executed.")
