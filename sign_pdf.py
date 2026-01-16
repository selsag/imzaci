import argparse
import getpass
import json
import logging
import os
import sys
import threading
import time
from pathlib import Path

# Suppress verbose logging from libraries
logging.getLogger('pyhanko').setLevel(logging.ERROR)
logging.getLogger('pikepdf').setLevel(logging.ERROR)
logging.getLogger('cryptography').setLevel(logging.ERROR)
logging.getLogger('urllib3').setLevel(logging.ERROR)
logging.getLogger().setLevel(logging.ERROR)

try:
    from pkcs11 import Attribute, ObjectClass, UserType, lib as pkcs11_lib
    # Ensure submodules are imported so PyInstaller picks them up
    try:
        import pkcs11.attributes  # noqa: F401
        import pkcs11.util  # noqa: F401
    except Exception:
        pass
except ImportError as exc:
    raise SystemExit('pkcs11 library is required; run "pip install pyHanko[pkcs11] python-pkcs11"') from exc

try:
    from cryptography import x509
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import hashes
except ImportError as exc:
    raise SystemExit('cryptography is required; run "pip install pyHanko[pkcs11]"') from exc

try:
    from pyhanko.sign import signers
    from pyhanko.sign.fields import SigFieldSpec
    from pyhanko.sign.pkcs11 import PKCS11Signer
except ImportError as exc:
    raise SystemExit('pyHanko is required; run "pip install pyHanko[pkcs11]"') from exc

CONFIG_DIR = Path(os.environ.get('USERPROFILE', Path.home())) / '.imzaci'
CONFIG_FILE = CONFIG_DIR / 'config.json'
DEFAULT_DLL = Path(r"C:\Windows\System32\akisp11.dll")

# Default signature/overlay settings (persisted under 'signature' in config)
DEFAULT_SIGNATURE_SETTINGS = {
    'width_mm': 4.5,     # font size in mm (formerly block width)
    'logo_width_mm': 20.0, # width of the logo image itself (mm)
    'margin_mm': 12.0,   # legacy single margin value (mm)
    'margin_x_mm': 12.0, # horizontal margin (mm)
    'margin_y_mm': 25.0, # vertical margin (mm)
    'placement': 'top-right',
}

# Placement options: internal code -> localized label (Turkish)
PLACEMENT_OPTIONS = [
    ('top-right', 'Sağ Üst'),
    ('top-left', 'Sol Üst'),
    ('bottom-right', 'Sağ Alt'),
    ('bottom-left', 'Sol Alt'),
    ('center', 'Orta'),
]


import tempfile

# Optional system tray support (pystray + PIL). If missing, a small taskbar helper window is used as a fallback.
try:
    import pystray
    from PIL import Image as PILImage, ImageDraw
    HAVE_PYSTRAY = True
except Exception:
    HAVE_PYSTRAY = False

# Temporary working dir for generated files (writable and persistent across runs)
TEMP_DIR = Path(tempfile.gettempdir()) / 'imzaci'
TEMP_DIR.mkdir(parents=True, exist_ok=True)

def cleanup_temp_cache():
    """Clean up old temporary files (older than 24 hours) to prevent stale file references."""
    try:
        import time
        now = time.time()
        max_age = 24 * 60 * 60  # 24 hours
        if TEMP_DIR.exists():
            for item in TEMP_DIR.iterdir():
                try:
                    if item.stat().st_mtime < now - max_age:
                        if item.is_file():
                            item.unlink()
                        elif item.is_dir():
                            import shutil
                            shutil.rmtree(item, ignore_errors=True)
                except Exception:
                    pass
    except Exception:
        pass

def resource_path(*parts):
    """Return path to resource, works both when running from source and from PyInstaller bundle."""
    if getattr(sys, 'frozen', False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parent
    return base.joinpath(*parts)

def create_combined_signature_image(logo_imza_path, signer_lines, font_size_mm, logo_width_mm, output_path=None, preview_mode=False, font_family=None, font_style='Normal'):
    """
    Creates a combined image (logo + signer text) for the signature block.
    Returns (PIL.Image, final_width_mm).
    """
    try:
        from PIL import Image as PILImage, ImageDraw, ImageFont
        from pathlib import Path as _Path
    except ImportError:
        return None, 0

    try:
        if not Path(logo_imza_path).exists():
            return None, 0
            
        logo_img = PILImage.open(str(logo_imza_path)).convert('RGBA')

        # Constant DPI for consistent text scaling relative to mm
        DPI = 300 if not preview_mode else 120
        px_per_mm = DPI / 25.4
        
        # Calculate pixel widths for components based on absolute mm
        px_w_logo = int(round(logo_width_mm * px_per_mm))
        
        # Set font size directly from user input (mm)
        scaled_font_size = max(8, int(round(font_size_mm * px_per_mm)))

        # Choose a font that supports Turkish and map short family names to actual font files
        font = None
        temp_img = PILImage.new('RGBA', (100, 100))
        draw_temp = ImageDraw.Draw(temp_img)
        test_chars = 'ĞÜŞİÖÇğüşıöç'

        # Map short family names (UI) to common Windows font files (fallback list)
        family_map = {
            'Segoe': r'C:\Windows\Fonts\segoeui.ttf',
            'Arial': r'C:\Windows\Fonts\arial.ttf',
            'Times': r'C:\Windows\Fonts\times.ttf',
            'Verdana': r'C:\Windows\Fonts\verdana.ttf',
            'Tahoma': r'C:\Windows\Fonts\tahoma.ttf',
            'Courier': r'C:\Windows\Fonts\cour.ttf'
        }

        def try_load_font(candidates, size):
            for fname in candidates:
                try:
                    f = ImageFont.truetype(fname, size)
                    bbox = draw_temp.textbbox((0, 0), test_chars, font=f)
                    if bbox[2] - bbox[0] > 0:
                        return f
                except Exception:
                    continue
            return None

        # Build candidates from provided family or sensible defaults
        if font_family:
            fam_key = str(font_family).strip()
            # Allow 'Segoe UI' or 'Segoe'
            fam_base = fam_key.split()[0]
            mapped = family_map.get(fam_base)
            if mapped:
                font_candidates = [mapped]
            else:
                # If user passed a path, try it directly
                font_candidates = [font_family]
        else:
            font_candidates = list(family_map.values()) + [
                'DejaVuSans.ttf',
                r'C:\Windows\Fonts\seguiemj.ttf'
            ]

        font = try_load_font(font_candidates, scaled_font_size)
        if font is None:
            font = ImageFont.load_default()

        # Determine bold/italic variants without changing font size
        bold_font = None
        italic_font = None
        
        if font_style and 'Bold' in font_style:
            bold_candidates = []
            # family-specific bold files heuristics
            try:
                if font_family:
                    fam_key = str(font_family).split()[0]
                    if fam_key == 'Segoe':
                        bold_candidates.append(r'C:\Windows\Fonts\segoeuib.ttf')
                    elif fam_key == 'Arial':
                        bold_candidates.append(r'C:\Windows\Fonts\arialbd.ttf')
                    elif fam_key == 'Tahoma':
                        bold_candidates.append(r'C:\Windows\Fonts\tahomabd.ttf')
                    elif fam_key == 'Verdana':
                        bold_candidates.append(r'C:\Windows\Fonts\verdanab.ttf')
                    elif fam_key == 'Times':
                        bold_candidates.append(r'C:\Windows\Fonts\timesbd.ttf')
                    elif fam_key == 'Courier':
                        bold_candidates.append(r'C:\Windows\Fonts\courbd.ttf')
            except Exception:
                pass
            # Generic fallbacks
            bold_candidates += [
                r'C:\Windows\Fonts\segoeuib.ttf',
                r'C:\Windows\Fonts\arialbd.ttf',
                'DejaVuSans-Bold.ttf'
            ]
            bold_font = try_load_font(bold_candidates, scaled_font_size)
        
        if font_style and 'Italic' in font_style:
            italic_candidates = []
            # family-specific italic files heuristics
            try:
                if font_family:
                    fam_key = str(font_family).split()[0]
                    if fam_key == 'Segoe':
                        italic_candidates.append(r'C:\Windows\Fonts\segoeuii.ttf')
                    elif fam_key == 'Arial':
                        italic_candidates.append(r'C:\Windows\Fonts\ariali.ttf')
                    elif fam_key == 'Tahoma':
                        italic_candidates.append(r'C:\Windows\Fonts\tahomai.ttf')
                    elif fam_key == 'Verdana':
                        italic_candidates.append(r'C:\Windows\Fonts\verdanai.ttf')
                    elif fam_key == 'Times':
                        italic_candidates.append(r'C:\Windows\Fonts\timesi.ttf')
                    elif fam_key == 'Courier':
                        italic_candidates.append(r'C:\Windows\Fonts\couri.ttf')
            except Exception:
                pass
            # Generic fallbacks
            italic_candidates += [
                r'C:\Windows\Fonts\segoeuii.ttf',
                r'C:\Windows\Fonts\ariali.ttf',
                'DejaVuSans-Oblique.ttf'
            ]
            italic_font = try_load_font(italic_candidates, scaled_font_size)

        # Use italic if specified, else bold if specified, else normal
        if italic_font:
            final_font = italic_font
        elif bold_font:
            final_font = bold_font
        else:
            final_font = font
        
        # Measure actual text width needed (no wrapping)
        max_line_w_px = 0
        measure_fnt = final_font
        for line in signer_lines:
            try:
                bbox = draw_temp.textbbox((0, 0), line, font=measure_fnt)
                max_line_w_px = max(max_line_w_px, bbox[2] - bbox[0])
            except Exception:
                max_line_w_px = max(max_line_w_px, len(line) * scaled_font_size * 0.6)
        
        # Add small safety margin for text (4px each side)
        px_w_text = int(max_line_w_px + 8)
        text_width_mm = px_w_text / px_per_mm

        # Total width of the block is the maximum of logo and text widths
        final_width_mm = max(text_width_mm, logo_width_mm, 1.0)
        canvas_w = int(round(final_width_mm * px_per_mm))

        # Scale logo to its absolute px width
        try:
            l_scale = px_w_logo / float(logo_img.width) if logo_img.width > 0 else 1.0
            resized_logo = logo_img.resize((px_w_logo, int(round(logo_img.height * l_scale))), PILImage.LANCZOS)
        except Exception:
            resized_logo = logo_img

        # Re-calculate padding and heights with the final font
        # Significantly narrower padding (0.4mm) for a very compact look
        padding = max(1, int(round(0.4 * px_per_mm)))
        
        # Use consistent line height based on font metrics instead of individual bounding boxes
        ascent, descent = measure_fnt.getmetrics()
        # Reduce fixed_line_h slightly by removing some of the font's internal leading (descent) 
        # to make lines even closer
        fixed_line_h = ascent + int(descent * 0.5)
        line_heights = [fixed_line_h] * len(signer_lines)

        total_text_h = sum(line_heights) + padding * (len(signer_lines) - 1)
        
        # Margins around the whole block
        top_margin = int(round(2.0 * px_per_mm)) # 2mm
        bottom_margin = int(round(3.0 * px_per_mm)) # 3mm

        # Dynamic height calculation: logo + text + margins
        # Base height from logo
        dynamic_h = resized_logo.height + top_margin + bottom_margin
        
        # Add height for main text block (now includes "İmzalayan:" at the beginning)
        dynamic_h += total_text_h

        # Add extra safety margin at bottom to prevent any clipping
        dynamic_h += padding * 3

        new_h = int(dynamic_h)
        new_img = PILImage.new('RGBA', (canvas_w, new_h), (255, 255, 255, 0))
        
        # Center logo horizontally
        paste_x = (canvas_w - resized_logo.width) // 2
        new_img.paste(resized_logo, (paste_x, top_margin))
        
        draw2 = ImageDraw.Draw(new_img)
        text_y_px = resized_logo.height + top_margin + padding
        
        # Add "e-imzalıdır" tag removed per user request (it's already in the logo image)

        for i, line in enumerate(signer_lines):
            render_font = final_font
            try:
                bbox = draw2.textbbox((0, 0), line, font=render_font)
                txt_w = bbox[2] - bbox[0]
                cx = (canvas_w - txt_w) // 2 - bbox[0]
                draw2.text((cx, text_y_px), line, fill=(0, 0, 0, 255), font=render_font)
            except Exception:
                draw2.text((4, text_y_px), line, fill=(0, 0, 0, 255))
            text_y_px += line_heights[i] + padding

        if output_path:
            new_img.save(output_path)
        return new_img, final_width_mm
    except Exception as e:
        print(f"Error in create_combined_signature_image: {e}")
        return None, 0
    except Exception as e:
        print(f"Error in create_combined_signature_image: {e}")
        return None

def apply_logo_xobject(in_path, overlay_path, out_path, add_to_all_pages=True, size_scale=0.8, placement='top-right', margin_x=None, margin_y=None, margin=None, target_width_mm=None):
    """Apply the overlay image as a single XObject and reference it on target pages.
    Returns True on success, False on failure.
    This is best-effort: if pikepdf is not available or an error occurs, it returns False.
    """
    try:
        import pikepdf
    except Exception:
        return False

    # Normalize margin args (points). Backwards-compat: `margin` may be provided and is treated as both axes.
    try:
        if margin_x is None:
            margin_x = float(margin) if margin is not None else 20.0
        if margin_y is None:
            margin_y = float(margin) if margin is not None else 20.0
    except Exception:
        margin_x = margin_y = 20.0

    in_path = Path(in_path)
    overlay_path = Path(overlay_path)
    out_path = Path(out_path)

    try:
        with pikepdf.open(in_path) as pdf, pikepdf.open(overlay_path) as overlay:
            page = overlay.pages[0]
            res = page.get('/Resources')
            xobj = res.get('/XObject') if res else None
            if not xobj:
                return False

            # find first image XObject
            img_obj = None
            for name, obj in xobj.items():
                try:
                    if obj['/Subtype'] == pikepdf.Name('/Image'):
                        img_obj = obj
                        break
                except Exception:
                    continue
            if img_obj is None:
                return False

            copied_img = pdf.copy_foreign(img_obj)

            # copy SMask if present
            try:
                smask = img_obj.get('/SMask')
                if smask is not None:
                    copied_smask = pdf.copy_foreign(smask)
                    copied_img['/SMask'] = copied_smask
            except Exception:
                pass

            pages_to_modify = pdf.pages if add_to_all_pages else [pdf.pages[0]]
            for p in pages_to_modify:
                resources = p.get('/Resources')
                if resources is None:
                    resources = pikepdf.Dictionary()
                    p['/Resources'] = resources
                xobjects = resources.get('/XObject')
                if xobjects is None:
                    xobjects = pikepdf.Dictionary()
                    resources['/XObject'] = xobjects
                name = pikepdf.Name('/LogoImg')
                xobjects[name] = copied_img

                # compute page box
                try:
                    media = p['/MediaBox']
                    llx = float(media[0])
                    lly = float(media[1])
                    urx = float(media[2])
                    ury = float(media[3])
                    page_width = urx - llx
                    page_height = ury - lly
                except Exception:
                    page_width = 595.0
                    page_height = 842.0

                # calculate image size (use native with scale or explicit target width if given)
                try:
                    img_w = float(copied_img.get('/Width'))
                    img_h = float(copied_img.get('/Height'))
                    if target_width_mm is not None:
                        try:
                            # convert mm -> points (1in = 25.4mm, 1pt = 1/72in)
                            desired_w = (float(target_width_mm) / 25.4) * 72.0
                        except Exception:
                            desired_w = min(img_w, page_width * 0.2) * size_scale
                    else:
                        desired_w = min(img_w, page_width * 0.2) * size_scale
                    scale = desired_w / img_w if img_w > 0 else size_scale
                    width_pt = desired_w
                    height_pt = img_h * scale
                except Exception:
                    width_pt = 100.0 * size_scale
                    height_pt = 40.0 * size_scale

                # placement: use margin_x/margin_y (points)
                try:
                    mx = float(margin_x)
                    my = float(margin_y)
                except Exception:
                    try:
                        mx = my = float(margin) if margin is not None else 20.0
                    except Exception:
                        mx = my = 20.0

                if placement == 'top-right':
                    x_pt = page_width - mx - width_pt
                    y_pt = page_height - my - height_pt
                elif placement == 'top-left':
                    x_pt = mx
                    y_pt = page_height - my - height_pt
                elif placement == 'bottom-right':
                    x_pt = page_width - mx - width_pt
                    y_pt = my
                elif placement == 'bottom-left':
                    x_pt = mx
                    y_pt = my
                elif placement == 'center':
                    x_pt = (page_width - width_pt) / 2.0 + mx
                    y_pt = (page_height - height_pt) / 2.0 + my
                else:
                    # Varsayılan olarak sağ üst (top-right)
                    x_pt = page_width - mx - width_pt
                    y_pt = page_height - my - height_pt

                do_stream = f'q {width_pt:.2f} 0 0 {height_pt:.2f} {x_pt:.2f} {y_pt:.2f} cm /LogoImg Do Q\n'.encode('utf-8')
                new_stream = pdf.make_stream(do_stream)
                cs = p.get('/Contents')
                try:
                    if isinstance(cs, pikepdf.Array):
                        cs.append(new_stream)
                    else:
                        p['/Contents'] = pikepdf.Array([cs, new_stream])
                except Exception:
                    p['/Contents'] = pikepdf.Array([new_stream])

            # Save with care: avoid aggressive recompress for big files
            try:
                size_in = in_path.stat().st_size
                if size_in > 10 * 1024 * 1024:
                    pdf.save(out_path)
                else:
                    pdf.remove_unreferenced_resources()
                    pdf.save(out_path, compress_streams=True, recompress_flate=True, normalize_content=True)
            except Exception:
                pdf.save(out_path)

        return True
    except Exception:
        return False


def load_config():
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            return {}
    return {}


def save_config(data):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(data, indent=2), encoding='utf-8')


def ensure_config():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def format_error(exc):
    text = str(exc)
    return text if text else repr(exc)



def load_pkcs11_lib(path):
    lib_path = Path(path)
    if not lib_path.exists():
        # Try to resolve the path in case it's a symlink or on a mounted drive
        try:
            resolved = lib_path.resolve()
            if resolved.exists():
                lib_path = resolved
            else:
                raise FileNotFoundError(f'PKCS#11 module missing at {lib_path}')
        except Exception:
            raise FileNotFoundError(f'PKCS#11 module missing at {lib_path}')
    
    # Verify it's actually accessible (not just existing but on disconnected drive)
    try:
        _ = lib_path.stat()
    except OSError as e:
        raise FileNotFoundError(f'PKCS#11 module not accessible at {lib_path}: {e}')
    
    return pkcs11_lib(str(lib_path))


def is_pkcs11_provider(path):
    """Return True if the DLL at `path` exports common PKCS#11 symbols (best-effort).
    This function tries to load the DLL (ctypes) and look for C_GetFunctionList / C_GetFunctionListEx / C_Initialize.
    It unloads the DLL after inspection. It may fail silently and return False.
    """
    try:
        import ctypes
        p = Path(path)
        if not p.exists():
            return False
        # Load the DLL with WinDLL to get stdcall exports
        try:
            lib = ctypes.WinDLL(str(p))
        except Exception:
            try:
                lib = ctypes.CDLL(str(p))
            except Exception:
                return False
        try:
            for sym in ('C_GetFunctionList', 'C_GetFunctionListEx', 'C_Initialize', 'C_GetSlotList'):
                try:
                    getattr(lib, sym)
                    return True
                except AttributeError:
                    continue
            return False
        finally:
            try:
                handle = lib._handle
                ctypes.windll.kernel32.FreeLibrary(handle)
            except Exception:
                pass
    except Exception:
        return False


def has_tokens_in_pkcs11_lib(path):
    """Return True if the PKCS#11 module at `path` reports any tokens (best-effort).
    This uses an external subprocess probe to isolate potential vendor crashes.
    Falls back to in-process checks only if the subprocess approach isn't available.
    """
    try:
        p = Path(path)
        if not p.exists():
            return False
        # Probe for tokens in a subprocess to avoid crashing the main process
        try:
            import subprocess, sys, json, os
            # Check if we're running from a PyInstaller bundle
            if getattr(sys, '_MEIPASS', None):
                # In bundle, avoid subprocess to prevent exe argument parser conflicts
                try:
                    from pkcs11 import lib as _lib
                    lib = _lib(str(p))
                    slots = list(lib.get_slots(token_present=True))
                    result = len(slots) > 0
                    return result
                except Exception:
                    return False
            else:
                # Running from source, use inline probe
                probe_script = """
import sys
import json
try:
    from pkcs11 import lib as _lib
    path = sys.argv[1]
    lib = _lib(path)
    for slot in lib.get_slots(token_present=True):
        print("1")
        sys.exit(0)
    print("0")
    sys.exit(0)
except Exception as e:
    sys.exit(2)
"""
                proc = subprocess.run(
                    [sys.executable, '-c', probe_script, str(p)],
                    capture_output=True,
                    timeout=5,
                    cwd=os.getcwd()
                )
            if proc.returncode == 0:
                out = proc.stdout.decode('utf-8', errors='ignore').strip()
                result = out == '1'
                return result
            else:
                # non-zero return (2) means probe failed; treat as no tokens
                return False
        except subprocess.TimeoutExpired:
            return False
        except Exception:
            return False
    except Exception:
        return False


def find_pkcs11_candidates(only_valid_providers=False, debug=False, use_path=False):
    """Return an ordered list of candidate PKCS#11 DLL paths found on the system.
    Uses a prioritized search order (System32, SysWOW64, Sysnative, known filenames, Program Files patterns, PATH).
    If only_valid_providers=True, attempt to detect which DLLs export PKCS#11 entrypoints and return only those.

    When debug=True, returns a dict {'candidates': [...], 'scanned_dirs': [...]}
    """

    candidates = []
    scanned_dirs = []

    if os.name != 'nt':
        return {'candidates': candidates, 'scanned_dirs': scanned_dirs} if debug else candidates

    system_root = os.environ.get('SystemRoot', r'C:\Windows')
    sys32 = Path(system_root) / 'System32'
    syswow = Path(system_root) / 'SysWOW64'
    sysnative = Path(system_root) / 'Sysnative'
    scanned_dirs.extend([str(sys32), str(syswow), str(sysnative)])

    prog_files = [os.environ.get('ProgramFiles'), os.environ.get('ProgramFiles(x86)')]

    # Exclude large / noisy Program Files locations per user request
    excluded_paths = {str(Path(r'C:\Program Files')), str(Path(r'C:\Program Files (x86)')), str(Path(r'C:\Program Files\SafeNet'))}
    prog_files = [p for p in prog_files if p and str(Path(p)) not in excluded_paths]

    # prioritized explicit paths and additional common filenames
    explicit_filenames = [
        'akisp11.dll', 'eTPKCS11.dll', 'dkck201.dll', 'palmap11.dll', 'palmaPkcs11.dll',
        'bit4xpki.dll', 'bit4idpkcs11.dll', 'opensc-pkcs11.dll', 'pkcs11.dll', 'cryptoki.dll',
        'libbit4ipki.dll', 'esebegi.dll', 'etpkcs11.dll', 'pgp-pkcs11.dll'
    ]

    explicit = [sys32 / name for name in explicit_filenames] + [syswow / name for name in explicit_filenames]
    # also include sysnative paths (when running 32-bit python on 64-bit windows)
    explicit += [sysnative / name for name in explicit_filenames]

    for p in explicit:
        try:
            # Verify the path is actually accessible (not just existing but on disconnected drive)
            if p.exists():
                try:
                    _ = p.stat()  # Will raise OSError if on unmounted drive
                    if p not in candidates:
                        candidates.append(p)
                except OSError:
                    # Path exists but is inaccessible (e.g., disconnected USB)
                    pass
        except Exception:
            pass

    # search common vendor/program paths with patterns
    patterns = ['**/*pkcs11*.dll', '**/*p11*.dll', '**/eTPKCS11.dll', '**/dkck201.dll', '**/akisp11.dll', '**/*pkcs11*.DLL']
    vendor_subdirs = ['SafeNet', 'Gemalto', 'Thales', 'Palma', 'Bit4id', 'OpenSC Project', 'AKIS', 'eToken', 'Aladdin']

    # Search Program Files and PATH
    for base in prog_files:
        if not base:
            continue
        basep = Path(base)
        scanned_dirs.append(str(basep))
        # vendor subdirectories
        for sub in vendor_subdirs:
            vendorp = basep / sub
            if vendorp.exists():
                scanned_dirs.append(str(vendorp))
                try:
                    for pattern in patterns:
                        for match in vendorp.rglob(pattern):
                            try:
                                _ = match.stat()  # Verify accessibility
                                if match not in candidates:
                                    candidates.append(match)
                            except OSError:
                                # File exists but inaccessible
                                pass
                except Exception:
                    pass

        # general search in program files
        try:
            for pattern in patterns:
                for match in basep.rglob(pattern):
                    try:
                        _ = match.stat()  # Verify accessibility
                        if match not in candidates:
                            candidates.append(match)
                    except OSError:
                        # File exists but inaccessible
                        pass
        except Exception:
            pass

    # final scan of System32 and Sysnative for any remaining patterns
    try:
        for pattern in ['**/*pkcs11*.dll', '**/*p11*.dll']:
            for match in sys32.rglob(pattern):
                try:
                    _ = match.stat()  # Verify accessibility
                    if match not in candidates:
                        candidates.append(match)
                except OSError:
                    pass
    except Exception:
        pass

    try:
        for pattern in ['**/*pkcs11*.dll', '**/*p11*.dll']:
            for match in sysnative.rglob(pattern):
                try:
                    _ = match.stat()  # Verify accessibility
                    if match not in candidates:
                        candidates.append(match)
                except OSError:
                    pass
    except Exception:
        pass

    # Search directories in PATH as a last resort (fast, non-recursive)
    if use_path:
        try:
            path_dirs = os.environ.get('PATH', '').split(os.pathsep)
            for d in path_dirs:
                try:
                    dd = Path(d)
                    if dd.exists() and str(dd) not in scanned_dirs:
                        scanned_dirs.append(str(dd))
                        for name in explicit_filenames:
                            cand = dd / name
                            if cand.exists() and cand not in candidates:
                                candidates.append(cand)
                except Exception:
                    continue
        except Exception:
            pass

    if only_valid_providers:
        # filter by checking for PKCS#11 entrypoints
        valid = []
        for p in candidates:
            try:
                if is_pkcs11_provider(p):
                    valid.append(p)
            except Exception:
                continue
        return ({'candidates': valid, 'scanned_dirs': scanned_dirs} if debug else valid)

    return ({'candidates': candidates, 'scanned_dirs': scanned_dirs} if debug else candidates)

def list_slots(lib):
    for slot in lib.get_slots(token_present=True):
        yield slot


def open_session(token, pin=None):
    return token.open(user_pin=pin)


def list_certs(lib, slot=None, token_label=None, pin=None):
    slots = [slot] if slot else list(lib.get_slots(token_present=True))
    for slot in slots:
        token = slot.get_token()
        if token_label and token.label and token_label.strip() not in token.label:
            continue
        with open_session(token, pin=pin) as session:
            for cert in session.get_objects({Attribute.CLASS: ObjectClass.CERTIFICATE}):
                value = cert[Attribute.VALUE]
                cert_obj = x509.load_der_x509_certificate(value, default_backend())
                try:
                    label = cert[Attribute.LABEL]
                except Exception:
                    label = '<no label>'
                subject = cert_obj.subject.rfc4514_string()
                issuer = cert_obj.issuer.rfc4514_string()
                yield slot, token, label, subject, issuer, cert_obj.serial_number


def list_slots_cmd(args):
    lib = load_pkcs11_lib(args.pkcs11_lib)
    for slot in list_slots(lib):
        token = slot.get_token()
        label = token.label or '<unknown>'
        print(f'Slot {slot.slot_id}: {label.strip()} serial {token.serial_number or "-"}')


def list_keys_cmd(args):
    lib = load_pkcs11_lib(args.pkcs11_lib)
    found = False
    for slot, token, label, subject, issuer, serial in list_certs(lib):
        found = True
        print(f'Slot {slot.slot_id} token "{token.label}" label "{label}" subject "{subject}" issuer "{issuer}"')
    if not found:
        print('No certificates found on the token')


def derive_slot(lib):
    slots = list(lib.get_slots(token_present=True))
    if not slots:
        raise RuntimeError('No token slots available')
    return slots[0]


def sign_cmd(args, add_logo_all_pages=True, use_xobject_opt=True, gui_logger=None):
    lib = load_pkcs11_lib(args.pkcs11_lib)
    slot = derive_slot(lib)
    token = slot.get_token()

    def first_cert_label(session):
        for cert in session.get_objects({Attribute.CLASS: ObjectClass.CERTIFICATE}):
            try:
                return cert[Attribute.LABEL]
            except Exception:
                continue
        return None

    with token.open(user_pin=args.pin) as session:
        cert_label = args.cert_label
        key_label = args.key_label or cert_label
        if not key_label:
            auto_label = first_cert_label(session)
            if auto_label:
                key_label = auto_label
                cert_label = cert_label or auto_label
        if not key_label:
            raise RuntimeError('Private key label bulunamadı; GUI veya --list-keys ile seçmeyi deneyin')

        # helper: log to GUI if available, otherwise fallback to print
        def _log(msg):
            # Suppress a few noisy informational messages per user preference
            try:
                suppress_substrings = (
                    'Signing succeeded with use_raw=',
                    'Signed ',
                    'XObject optimizasyonu uygulandı',
                    'Using font:',
                    '✓ İmzalandı:',
                    'Overlay page size:',
                    'pikepdf: temp_with_logo'
                )
                for s in suppress_substrings:
                    try:
                        if s in msg:
                            return
                    except Exception:
                        pass
                if gui_logger:
                    gui_logger(msg)
                else:
                    print(msg)
            except Exception:
                try:
                    print(msg)
                except Exception:
                    pass

        # Generate unique signature field name to avoid conflicts
        import time
        signature_field_name = f"Signature_{int(time.time())}"
        
        signer = PKCS11Signer(
            pkcs11_session=session,
            key_label=key_label,
            cert_label=cert_label,
            use_raw_mechanism=True,
            prefer_pss=True,
        )
        metadata = signers.PdfSignatureMetadata(reason=args.reason, location=args.location, field_name=signature_field_name)
        field_spec = SigFieldSpec(
            signature_field_name, 
            on_page=0,
            box=(350, 450, 580, 600),  # Sağ üst köşe
        )
        pdf_signer = signers.PdfSigner(
            signature_meta=metadata,
            signer=signer,
            timestamper=None,
        )
        
        # Logo'yu PDF'ye ekle (FPDF2 ile - transparency'yi daha iyi korur)
        from PyPDF2 import PdfReader, PdfWriter
        from PIL import Image as PILImage
        from fpdf import FPDF
        
        # Check config for custom signature image path
        sig_conf_init = load_config().get('signature', {})
        custom_sig_path = sig_conf_init.get('image_path')
        logo_imza_path = Path(custom_sig_path) if custom_sig_path and Path(custom_sig_path).exists() else resource_path('logo_imza.png')
        
        if logo_imza_path.exists():
            # FPDF2 ile overlay PDF oluştur - cache'den kullan
            temp_overlay = TEMP_DIR / 'temp_overlay.pdf'
            temp_overlay.parent.mkdir(parents=True, exist_ok=True)
            
            # Always regenerate the overlay for each signing so signer info is current and embedded
            # Determine input PDF page size so overlay aligns in merge fallback.
            try:
                with open(args.in_path, 'rb') as inf:
                    _reader = PdfReader(inf)
                    _m = _reader.pages[0].mediabox
                    pw_pt = float(_m[2]) - float(_m[0])
                    ph_pt = float(_m[3]) - float(_m[1])
                    page_w_mm = pw_pt / 72.0 * 25.4
                    page_h_mm = ph_pt / 72.0 * 25.4
            except Exception:
                # fallback to A4
                page_w_mm = 210.0
                page_h_mm = 297.0

            pdf = FPDF(unit='mm', format=(page_w_mm, page_h_mm))
            pdf.add_page()

            # Prepare and add signature image (logo_imza) first so XObject optimization picks it up
            logo_imza_for_pdf = None
            if logo_imza_path.exists():
                # Signature settings: width_mm, margin_mm, placement (GUI-configurable or from config file)
                try:
                    owner = getattr(gui_logger, '__self__', None)
                    sig_conf = owner.config.get('signature', {}) if owner else load_config().get('signature', {})

                except Exception:
                    sig_conf = load_config().get('signature', {})

                block_width_mm = float(sig_conf.get('width_mm', DEFAULT_SIGNATURE_SETTINGS['width_mm']))
                logo_width_mm = float(sig_conf.get('logo_width_mm', DEFAULT_SIGNATURE_SETTINGS.get('logo_width_mm', 15.0)))
                logo_margin_mm = float(sig_conf.get('margin_mm', DEFAULT_SIGNATURE_SETTINGS['margin_mm']))
                placement = sig_conf.get('placement', DEFAULT_SIGNATURE_SETTINGS['placement'])

                # Compute placement using separate X/Y margins (merge fallback uses mm).
                # Vertical margin is interpreted as distance from the nearest vertical edge
                try:
                    sig_conf_local = sig_conf or {}
                    margin_x_val = float(sig_conf_local.get('margin_x_mm', DEFAULT_SIGNATURE_SETTINGS['margin_mm']))
                    margin_y_val = float(sig_conf_local.get('margin_y_mm', DEFAULT_SIGNATURE_SETTINGS['margin_mm']))
                    # Use the margins directly for output placement.
                    margin_y_for_output = margin_y_val

                    # Estimate total block height (logo + text) for accurate placement
                    total_sig_height_mm = 20.0 # Default fallback
                    try:
                        img_for_dims = PILImage.open(str(logo_imza_path))
                        # Calculate logo height in mm
                        actual_logo_h_mm = (img_for_dims.height / img_for_dims.width) * logo_width_mm
                        # Estimate text height using the same heuristic as the GUI preview so positions match
                        # GUI uses: total_text_h_px = (num_lines * 175) + 110; then actual_text_h_mm = (total_text_h_px / 1000) * block_width_mm
                        # Use a conservative default of 3 lines when precise line-count isn't available
                        assumed_lines = 3
                        estimated_text_h_mm = ((assumed_lines * 175) + 110) / 1000.0 * block_width_mm
                        total_sig_height_mm = actual_logo_h_mm + estimated_text_h_mm
                        img_for_dims.close()
                    except Exception:
                        pass
                    logo_imza_height_mm = total_sig_height_mm

                    if placement == 'top-right':
                        logo_imza_x_mm = max(4.0, page_w_mm - margin_x_val - block_width_mm)
                        # use inverted vertical margin for output placement
                        logo_imza_y_mm = margin_y_for_output
                    elif placement == 'top-left':
                        logo_imza_x_mm = margin_x_val
                        logo_imza_y_mm = margin_y_for_output
                    elif placement == 'bottom-right':
                        logo_imza_x_mm = max(4.0, page_w_mm - margin_x_val - block_width_mm)
                        if logo_imza_height_mm is not None:
                            logo_imza_y_mm = max(4.0, page_h_mm - margin_y_for_output - logo_imza_height_mm)
                        else:
                            # fallback: use a conservative estimate (similar heuristic used previously)
                            logo_imza_y_mm = max(4.0, page_h_mm - margin_y_for_output - (logo_width_mm * 0.4))
                    elif placement == 'bottom-left':
                        logo_imza_x_mm = margin_x_val
                        if logo_imza_height_mm is not None:
                            logo_imza_y_mm = max(4.0, page_h_mm - margin_y_for_output - logo_imza_height_mm)
                        else:
                            logo_imza_y_mm = max(4.0, page_h_mm - margin_y_for_output - (logo_width_mm * 0.4))
                    elif placement == 'center':
                        logo_imza_x_mm = (page_w_mm - block_width_mm) / 2.0 + margin_x_val
                        if logo_imza_height_mm is not None:
                            logo_imza_y_mm = (page_h_mm - logo_imza_height_mm) / 2.0 + margin_y_for_output
                        else:
                            logo_imza_y_mm = (page_h_mm - logo_width_mm * 0.4) / 2.0 + margin_y_for_output
                    else:
                        # Default: place at top-right semantics
                        logo_imza_x_mm = max(4.0, page_w_mm - margin_x_val - block_width_mm)
                        logo_imza_y_mm = margin_y_for_output
                except Exception:
                    logo_imza_x_mm = min(188, page_w_mm - block_width_mm)
                    logo_imza_y_mm = min(210, page_h_mm - 4)
                try:
                    # show localized placement label in logs when possible
                    pl_label = next((lbl for code, lbl in PLACEMENT_OPTIONS if code == placement), placement)
                    _log(f'Overlay page size: {page_w_mm:.2f}x{page_h_mm:.2f} mm; placing signature at x={logo_imza_x_mm:.2f} y={logo_imza_y_mm:.2f} (w={block_width_mm}mm) yerleşim={pl_label} yandan={margin_x_val}mm dikey={margin_y_val}mm')
                except Exception:
                    pass
                try:
                    # Build signer info lines
                    signer_lines = ["İmzalayan:"]
                    signer_name = None
                    cert_serial = None
                    cert_fp_short = None
                    cert_fp_full = None
                    try:
                        for cert in session.get_objects({Attribute.CLASS: ObjectClass.CERTIFICATE}):
                            try:
                                lbl = cert[Attribute.LABEL]
                            except Exception:
                                lbl = None
                            if lbl and cert_label and lbl == cert_label:
                                try:
                                    cert_der = cert[Attribute.VALUE]
                                    cert_obj = x509.load_der_x509_certificate(cert_der, default_backend())
                                    try:
                                        from cryptography.x509.oid import NameOID
                                        cn_attrs = cert_obj.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
                                        if cn_attrs:
                                            signer_name = cn_attrs[0].value
                                    except Exception:
                                        signer_name = None
                                    try:
                                        cert_serial = cert_obj.serial_number
                                    except Exception:
                                        cert_serial = None

                                    # SHA-256 fingerprint (full hex and short form for image)
                                    try:
                                        fp = cert_obj.fingerprint(hashes.SHA256()).hex().upper()
                                        cert_fp_full = fp
                                        cert_fp_short = fp[:32]
                                    except Exception:
                                        cert_fp_full = None
                                        cert_fp_short = None

                                    # Log detailed certificate info to GUI log for review
                                    try:
                                        issuer = cert_obj.issuer.rfc4514_string()
                                    except Exception:
                                        issuer = None
                                    try:
                                        # Use UTC-aware properties if available to avoid deprecation warnings
                                        nb = getattr(cert_obj, 'not_valid_before_utc', None) or getattr(cert_obj, 'not_valid_before', None)
                                        na = getattr(cert_obj, 'not_valid_after_utc', None) or getattr(cert_obj, 'not_valid_after', None)
                                        not_before = nb.date() if nb is not None else None
                                        not_after = na.date() if na is not None else None
                                    except Exception:
                                        not_before = None
                                        not_after = None
                                    try:
                                        sig_alg = cert_obj.signature_algorithm_oid._name
                                    except Exception:
                                        sig_alg = getattr(cert_obj.signature_algorithm_oid, 'dotted_string', str(cert_obj.signature_algorithm_oid))
                                    try:
                                        pub = cert_obj.public_key()
                                        key_type = pub.__class__.__name__
                                    except Exception:
                                        key_type = None
                                    try:
                                        fprint = cert_fp_full
                                    except Exception:
                                        fprint = None

                                except Exception:
                                    pass
                                break
                    except Exception:
                        pass

                    if not signer_name:
                        try:
                            # If called from GUI, gui_logger may be a bound method whose __self__ is the GUIApp
                            owner = getattr(gui_logger, '__self__', None)
                            if owner and getattr(owner, 'cert_info_var', None) and owner.cert_info_var.get():
                                signer_name = owner.cert_info_var.get().split('|')[-1].strip()
                            elif cert_label:
                                signer_name = cert_label
                            else:
                                signer_name = 'İmzacı'
                        except Exception:
                            signer_name = 'İmzacı'

                    try:
                        token_id = f"Slot {slot.slot_id}"
                        token_label = (token.label or '').strip()
                        if token_label:
                            token_id += f" ({token_label})"
                        token_serial = token.serial_number or None
                    except Exception:
                        token_id = None
                        token_serial = None

                    try:
                        from datetime import datetime
                        ts = datetime.now().astimezone()
                        # Date only, format dd.mm.yyyy
                        ts_text = ts.strftime('%d.%m.%Y')
                    except Exception:
                        ts_text = ''
                    # Put name on a separate line
                    if signer_name:
                        signer_lines.append(signer_name)
                    if ts_text:
                        signer_lines.append(f'Tarih: {ts_text}')

                    if cert_serial:
                        signer_lines.append(f'SN: {cert_serial}')


                except Exception:
                    signer_lines = []

                # Compose combined image (logo + text) so it survives XObject copy
                try:
                    logo_imza_for_pdf = logo_imza_path
                    combined_created = False
                    if signer_lines:
                        combined_path = TEMP_DIR / f'logo_imza_with_text.png'
                        # Respect configured font family/style when creating combined image
                        font_family_cfg = sig_conf.get('font_family') if sig_conf else None
                        font_style_cfg = sig_conf.get('font_style', 'Normal') if sig_conf else 'Normal'
                        result_img, actual_w_mm = create_combined_signature_image(
                            logo_imza_path=logo_imza_path,
                            signer_lines=signer_lines,
                            font_size_mm=block_width_mm,
                            logo_width_mm=logo_width_mm,
                            output_path=combined_path,
                            font_family=font_family_cfg,
                            font_style=font_style_cfg
                        )
                        if result_img:
                            # Use the generated combined image directly for embedding in the overlay PDF.
                            logo_imza_for_pdf = combined_path
                            block_width_mm = actual_w_mm # Use the calculated total width for PDF placement
                            combined_created = True
                        else:
                            logo_imza_for_pdf = logo_imza_path
                            combined_created = False
                    else:
                        logo_imza_for_pdf = logo_imza_path
                except Exception as e:
                    try:
                        _log(f'Error creating combined signature image: {e}')
                    except Exception:
                        pass
                    logo_imza_for_pdf = logo_imza_path

                # If we could not create a combined image but signer_lines exist, disable XObject optimization so text is preserved via PDF text fallback
                try:
                    if signer_lines and logo_imza_for_pdf == logo_imza_path:
                        _log('Combined image creation failed; disabling XObject optimization to preserve signer text')
                        use_xobject_flag = False
                except Exception:
                    pass

                # place signature image first
                try:
                    pdf.image(str(logo_imza_for_pdf), x=logo_imza_x_mm, y=logo_imza_y_mm, w=block_width_mm)
                except Exception:
                    try:
                        pdf.image(str(logo_imza_path), x=logo_imza_x_mm, y=logo_imza_y_mm, w=block_width_mm)
                    except Exception:
                        pass

            pdf.output(str(temp_overlay))
            
            # Try XObject-based optimization first if requested
            temp_with_logo = TEMP_DIR / 'temp_with_logo.pdf'
            temp_with_logo.parent.mkdir(parents=True, exist_ok=True)
            used_xobject = False
            # honor CLI flag if present, otherwise default to the `use_xobject_opt` parameter (now True by default)
            use_xobject_flag = getattr(args, 'use_xobject_opt', use_xobject_opt)
            if use_xobject_flag:
                try:
                    try:
                        # Convert X/Y margins from mm -> pt for pikepdf placement
                        try:
                            margin_x_pt = (margin_x_val / 25.4) * 72.0
                            margin_y_pt = (margin_y_for_output / 25.4) * 72.0
                        except Exception:
                            margin_x_pt = margin_y_pt = 20.0
                    except Exception:
                        margin_x_pt = margin_y_pt = 20.0
                    try:
                        success = apply_logo_xobject(args.in_path, temp_overlay, temp_with_logo, add_to_all_pages=add_logo_all_pages, size_scale=0.8, placement=placement, margin_x=margin_x_pt, margin_y=margin_y_pt, target_width_mm=block_width_mm)
                        if success:
                            used_xobject = True
                        else:
                            _log('XObject optimizasyonu uygulanamadı, fallback ile devam ediliyor')
                    except Exception as e:
                        _log(f'XObject optimizasyonunda hata, fallback ile devam ediliyor: {e}')
                except Exception as e:
                    _log(f'XObject optimizasyonunda hata, fallback ile devam ediliyor: {e}')

            if not used_xobject:
                # PyPDF2 ile merge - hızlı merge, compression yok (büyük olsa da hızlı)
                with open(args.in_path, 'rb') as inf:
                    reader = PdfReader(inf)
                    with open(temp_overlay, 'rb') as overlay_f:
                        overlay_reader = PdfReader(overlay_f)
                        overlay_page = overlay_reader.pages[0]
                        
                        writer = PdfWriter()
                        
                        # Logo ekleme stratejisi
                        if add_logo_all_pages:
                            # Her sayfaya overlay'i merge et (hızlı, sıkıştırma yok)
                            for page_num in range(len(reader.pages)):
                                page = reader.pages[page_num]
                                page.merge_page(overlay_page)
                                writer.add_page(page)
                        else:
                            # Sadece ilk sayfaya ekle
                            first_page = reader.pages[0]
                            first_page.merge_page(overlay_page)
                            writer.add_page(first_page)
                            
                            for page_num in range(1, len(reader.pages)):
                                writer.add_page(reader.pages[page_num])
                        
                        temp_with_logo = TEMP_DIR / 'temp_with_logo.pdf'
                        temp_with_logo.parent.mkdir(parents=True, exist_ok=True)
                        # Compression olmadan direkt yaz (hızlı)
                        with open(temp_with_logo, 'wb') as f:
                            writer.write(f)

            # Pre-sign optimization: pikepdf ile gereksiz nesneleri kaldır ve stream'leri optimize et
            try:
                import pikepdf
                with pikepdf.open(temp_with_logo, allow_overwriting_input=True) as pdf:
                    try:
                        # Remove unreferenced resources (if any)
                        pdf.remove_unreferenced_resources()
                    except Exception:
                        pass
                    # Save with stream optimization/compression (overwrite allowed)
                    pdf.save(temp_with_logo, compress_streams=True, recompress_flate=True, normalize_content=True)
                _log('pikepdf: temp_with_logo optimize edildi')
            except Exception as e:
                _log(f'pikepdf optimize atlandi: {e}')
            
            # Logo eklenen PDF'yi imzala
            from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
            from pyhanko.pdf_utils.reader import PdfFileReader

            # Use a robust fallback that does NOT reuse a possibly modified writer.
            # For each attempt, re-open the source PDF and write to a temp file; on success, atomically move to final path.
            def _sign_with_fallback(src_path, final_path):
                attempts = [
                    (True, True),  # initial: raw + prefer PSS
                    (True, False), # raw + no PSS
                    (False, False) # non-raw + no PSS
                ]
                last_exc = None
                for ur, ps in attempts:
                    tmp_out = None
                    try:
                        # create temporary output file
                        import tempfile, shutil
                        tmpf = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
                        tmp_out = tmpf.name
                        tmpf.close()

                        with open(src_path, 'rb+') as inf:
                            r = PdfFileReader(inf, strict=False)
                            w_try = IncrementalPdfFileWriter(inf, prev=r)
                            try:
                                signer_try = PKCS11Signer(
                                    pkcs11_session=session,
                                    key_label=key_label,
                                    cert_label=cert_label,
                                    use_raw_mechanism=ur,
                                    prefer_pss=ps,
                                )
                                pdf_signer_try = signers.PdfSigner(signature_meta=metadata, signer=signer_try, timestamper=None)
                                with open(tmp_out, 'wb') as outtmp:
                                    pdf_signer_try.sign_pdf(w_try, output=outtmp)
                                # success: move tmp to final
                                shutil.move(tmp_out, final_path)
                                _log(f'Signing succeeded with use_raw={ur} prefer_pss={ps}')
                                return
                            except NotImplementedError as e:
                                last_exc = e
                                _log(f'Falling back: use_raw={ur} prefer_pss={ps} failed: {e}')
                            except Exception as e:
                                last_exc = e
                                _log(f'Signing attempt failed (use_raw={ur} prefer_pss={ps}): {e}')
                                # If it's a field already exists error, raise user-friendly error
                                from pyhanko.sign.general import SigningError
                                if isinstance(e, SigningError) and 'Signature field with name' in str(e):
                                    raise RuntimeError('PDF already contains a filled signature field; please try again with a different timestamp or remove existing signatures') from e
                            finally:
                                # cleanup tmp if exists and failed
                                try:
                                    if tmp_out and os.path.exists(tmp_out):
                                        os.remove(tmp_out)
                                except Exception:
                                    pass
                    except Exception as e:
                        last_exc = e
                        _log(f'Signing infrastructure error: {e}')
                        # try next attempt
                        continue
                if last_exc:
                    raise last_exc

            _sign_with_fallback(str(temp_with_logo), str(args.out_path))
            
            # Geçici dosyaları temizle (overlay'i cache'de tut)
            temp_with_logo.unlink(missing_ok=True)
        else:
            # Logo yoksa direkt imzala
            from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
            from pyhanko.pdf_utils.reader import PdfFileReader
            # For the no-logo path, use the same robust fallback that re-opens the source for each attempt
            def _sign_with_fallback(src_path, final_path):
                attempts = [
                    (True, True),  # initial: raw + prefer PSS
                    (True, False), # raw + no PSS
                    (False, False) # non-raw + no PSS
                ]
                last_exc = None
                for ur, ps in attempts:
                    tmp_out = None
                    try:
                        import tempfile, shutil
                        tmpf = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
                        tmp_out = tmpf.name
                        tmpf.close()

                        with open(src_path, 'rb+') as inf:
                            r = PdfFileReader(inf, strict=False)
                            w_try = IncrementalPdfFileWriter(inf, prev=r)
                            try:
                                signer_try = PKCS11Signer(
                                    pkcs11_session=session,
                                    key_label=key_label,
                                    cert_label=cert_label,
                                    use_raw_mechanism=ur,
                                    prefer_pss=ps,
                                )
                                pdf_signer_try = signers.PdfSigner(signature_meta=metadata, signer=signer_try, timestamper=None)
                                with open(tmp_out, 'wb') as outtmp:
                                    pdf_signer_try.sign_pdf(w_try, output=outtmp)
                                # success: move tmp to final
                                shutil.move(tmp_out, final_path)
                                _log(f'Signing succeeded with use_raw={ur} prefer_pss={ps}')
                                return
                            except NotImplementedError as e:
                                last_exc = e
                                _log(f'Falling back: use_raw={ur} prefer_pss={ps} failed: {e}')
                            except Exception as e:
                                last_exc = e
                                _log(f'Signing attempt failed (use_raw={ur} prefer_pss={ps}): {e}')
                                from pyhanko.sign.general import SigningError
                                if isinstance(e, SigningError) and 'Signature field with name' in str(e):
                                    raise RuntimeError('PDF already contains a filled signature field; please try again with a different timestamp or remove existing signatures') from e
                            finally:
                                try:
                                    if tmp_out and os.path.exists(tmp_out):
                                        os.remove(tmp_out)
                                except Exception:
                                    pass
                    except Exception as e:
                        last_exc = e
                        _log(f'Signing infrastructure error: {e}')
                        continue
                if last_exc:
                    raise last_exc

            _sign_with_fallback(str(args.in_path), str(args.out_path))        



def build_cli_parser():
    parser = argparse.ArgumentParser(description='pyHanko PKCS#11 PDF signer')
    parser.add_argument('--pkcs11-lib', default=str(DEFAULT_DLL), help='PKCS#11 module DLL path')
    sub = parser.add_subparsers(dest='cmd')
    sub.required = True
    sub.add_parser('list-slots', help='List PKCS#11 slots/tokens')
    sub.add_parser('list-keys', help='List certificates')
    sign_p = sub.add_parser('sign', help='Sign PDF via PKCS#11 token')
    sign_p.add_argument('--in', dest='in_path', required=True)
    sign_p.add_argument('--out', dest='out_path', required=True)
    sign_p.add_argument('--pin', help='PIN (prompted if omitted)')
    sign_p.add_argument('--key-label', help='Private key label')
    sign_p.add_argument('--cert-label', help='Certificate label')
    sign_p.add_argument('--reason')
    sign_p.add_argument('--location')
    # CLI: default is enabled; provide a flag to explicitly disable if needed
    sign_p.add_argument('--no-xobject-opt', dest='use_xobject_opt', action='store_false', help='Disable XObject reuse optimization for logos')
    sign_p.set_defaults(use_xobject_opt=True)
    return parser


def run_cli():
    parser = build_cli_parser()
    # If invoked with no arguments, print help and exit cleanly (avoid argparse error exit code)
    if len(sys.argv) == 1:
        parser.print_help()
        return
    args = parser.parse_args()
    if args.cmd == 'list-slots':
        list_slots_cmd(args)
    elif args.cmd == 'list-keys':
        list_keys_cmd(args)
    elif args.cmd == 'sign':
        if not args.pin:
            args.pin = getpass.getpass('PIN: ')
        sign_cmd(args)



def main():
    """Entry point for CLI usage.
    
    This module serves as a backend signing engine.
    Use "python modern_gui_ttkbootstrap.py" for the GUI.
    """
    run_cli()


if __name__ == "__main__":
    main()
