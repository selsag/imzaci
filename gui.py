"""
Modern PDF signing GUI using ttkbootstrap.

A professional desktop application for digitally signing PDF documents with
PKCS#11-compatible tokens (smart cards, HSMs). Features include:
- Interactive PKCS#11 token and certificate management
- PDF file selection with signature placement controls
- Real-time signature preview and customization
- Professional ttkbootstrap UI with smooth animations
- Persistent configuration storage

Installation: pip install ttkbootstrap pyHanko[pkcs11] python-pkcs11 cryptography
"""

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap import Combobox
try:
    from ttkbootstrap_icons_bs import BootstrapIcon as TBIcon
except ImportError:
    TBIcon = None
from pathlib import Path
from tkinter import filedialog, messagebox, Toplevel, Label, Text
import threading
import os
import webbrowser
import math
try:
    from PIL import Image as PILImage, ImageTk
except ImportError:
    PILImage = None
try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None
try:
    import fitz  # type: ignore
except ImportError:
    fitz = None

# Import from sign_pdf backend
from sign_pdf import (
    DEFAULT_DLL,
    DEFAULT_SIGNATURE_SETTINGS,
    PLACEMENT_OPTIONS,
    TEMP_DIR,
    cleanup_temp_cache,
    resource_path,
    load_config,
    save_config,
    find_pkcs11_candidates,
    is_pkcs11_provider,
    load_pkcs11_lib,
    has_tokens_in_pkcs11_lib,
    list_certs,
    sign_cmd,
    create_combined_signature_image
)

# Import centralized constants
from constants import (
    APP_NAME, APP_VERSION, WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_THEME,
    DEFAULT_SIGNATURE_SETTINGS, PLACEMENT_OPTIONS,
    FONT_FAMILY, FONT_EMOJI_FAMILY, TITLE_FONT_SIZE, ICON_FONT_SIZE,
    ICON_SIZE_NORMAL, ICON_SIZE_LARGE, ICON_SIZE_HOVER
)


class BootstrapIcon:
    """Icon manager with hover state support for ttkbootstrap buttons.
    
    Handles loading and switching between normal and hover icon states.
    Falls back to emoji text if icon loading fails.
    
    Attributes:
        images (dict): Cached icon images for different states.
        widget (ttk.Widget): Associated widget.
        fallback_char (str): Fallback emoji/char if icon fails to load.
    """
    
    def __init__(self, name: str, fallback_char: str = "", states: list | None = None, size: int = 18):
        """Initialize icon manager.
        
        Args:
            name (str): Icon name from ttkbootstrap-icons-bs.
            fallback_char (str): Fallback character if icon loading fails.
            states (list): List of state configs (normal, hover). Default uses secondary/primary colors.
            size (int): Icon size in pixels. Default 18.
        """
        self.images = {}
        self.widget = None
        self.fallback_char = fallback_char
        
        # Type hints for widget - will be set by attach()
        self._widget_ref = None
        
        if TBIcon is None:
            pass
            return
            
        if not states:
            states = ({"name": name, "color": "secondary"}, {"name": name, "color": "primary"})
        
        style = ttk.Style()
        for i, state_name in enumerate(['normal', 'hover']):
            if i < len(states):
                cfg = states[i]
                c = cfg.get('color')
                # Duruma özel boyut varsa onu kullan, yoksa varsayılanı kullan
                s = cfg.get('size', size)
                # Resolve bootstyle color name to hex code if possible
                color_val = style.colors.get(c) if hasattr(style, 'colors') and c in style.colors else c
                icon_name = cfg.get('name', name)
                try:
                    # Use keyword arguments to avoid positional argument errors (str vs int)
                    img = TBIcon(name=icon_name, color=color_val, size=s)
                    self.images[state_name] = img
                except Exception:
                    pass
        self.image = self.images.get('normal')

    def attach(self, widget) -> None:
        """Attach icon to a widget with hover state support.
        
        Args:
            widget: Target widget to attach icon to.
        """
        self.widget = widget
        self._widget_ref = widget
        if self.image:
            widget.configure(image=self.image)
            # Use add='+' to preserve existing bindings and ensure reference is kept
            widget.bind('<Enter>', lambda e: self.set_state('hover'), add='+')
            widget.bind('<Leave>', lambda e: self.set_state('normal'), add='+')
            widget.image = self.image # Initial reference
        elif self.fallback_char:
            # Fallback to emoji text if icon failed to load
            try:
                current_text = widget.cget("text") or ""
                widget.configure(text=f"{self.fallback_char} {current_text.strip()}")
            except Exception:
                pass

    def set_state(self, state: str) -> None:
        """Change icon state (normal/hover).
        
        Args:
            state (str): Target state ('normal' or 'hover').
        """
        if self.widget and state in self.images:
            img = self.images[state]
            self.widget.configure(image=img)
            # Keep reference to prevent garbage collection
            self.widget.image = img

class CreateToolTip:
    """Create a tooltip for a given widget that recalculates position on show (multi-screen safe)."""
    def __init__(self, widget, text, root_window=None):
        self.widget = widget
        self.text = text
        self.root = root_window or widget.winfo_toplevel()  # Use provided root or find it
        self.tipwindow = None
        self.id = None
        self.x = self.y = 0
        # Bind events directly to show/hide tooltip
        self.widget.bind("<Enter>", self.showtip, add="+")
        self.widget.bind("<Leave>", self.hidetip, add="+")
    
    def showtip(self, event=None):
        """Display tooltip below the widget with fresh position calculation."""
        # Hide existing tooltip first to recalculate position
        self.hidetip()
        
        if not self.text:
            return
        try:
            # Get widget position and size (fresh calculation for multi-screen)
            x = self.widget.winfo_rootx() + self.widget.winfo_width() // 2
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
            
            # Create tooltip window - use main root for multi-screen support
            self.tipwindow = tw = Toplevel(self.root)
            tw.wm_overrideredirect(True)
            tw.attributes('-topmost', True)  # Ensure tooltip stays on top
            
            # Create label with text - light orange background with white text
            style = ttk.Style()
            style.configure("Tooltip.TLabel", background="#FFA500", foreground="white", padding=(4, 2))
            label = ttk.Label(tw, text=self.text, style="Tooltip.TLabel")
            label.pack(ipadx=2, ipady=2)
            
            # Position tooltip - offset to center horizontally
            tw.update_idletasks()
            tw_width = tw.winfo_width()
            tw.wm_geometry(f"+{max(0, x - tw_width // 2)}+{y}")
        except Exception:
            self.tipwindow = None
    
    def hidetip(self, event=None):
        """Hide tooltip."""
        if self.tipwindow:
            try:
                self.tipwindow.destroy()
            except Exception:
                pass
            self.tipwindow = None

class ModernTTKApp:
    """Main application class for the PDF signing GUI.
    
    Manages:
    - PKCS#11 token discovery and management
    - PDF file selection and signing
    - Signature placement and customization
    - Persistent configuration storage
    """
    
    def __init__(self):
        """Initialize the application and set up the UI."""
        # Clean up ALL temporary files before starting (fixes stale DPI/coordinate issues)
        cleanup_temp_cache()
        
        # Initialize image cache variables (clear any stale caches)
        self._sig_image_cache = None
        self._sig_image_cache_key = None
        self._bg_image_cache = None
        self._bg_image_cache_key = None
        self._embedded_bg_photo = None
        self._preview_bg_photo = None
        self._embedded_sig_photo = None
        self._preview_sig_photo = None

        # Create root window with ttkbootstrap theme
        self.root = ttk.Window(themename=WINDOW_THEME)
        self.root.title(APP_NAME)
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.resizable(True, True)
        
        # Load persisted configuration
        try:
            self.config = load_config()
        except Exception:
            self.config = {}
        
        # Eski dinamik şablonu temizle (Açılışta orijinal şablonun görünmesi için)
        try:
            dynamic_path = TEMP_DIR / 'dynamic_sablon.png'
            if dynamic_path.exists():
                dynamic_path.unlink()
        except Exception:
            pass

        # Drag-drop state variables
        self._is_dragging = False
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._drag_logo_x = 0
        self._drag_logo_y = 0

        self.build_ui()
        
        # Standard geometry realization (no hacks needed with proper grid layout)
        try:
            self.root.update_idletasks()
            self.root.update()
            # Center the window on screen after layout is realized
            try:
                self._center_window()
            except Exception:
                pass
        except Exception:
            pass

        # Move İmzala button to the PIN row (authentication area)
        try:
            self._add_sign_button_to_pin()
        except Exception:
            pass

        # Save on close to ensure latest signature settings persist
        try:
            self.root.protocol('WM_DELETE_WINDOW', self._on_close)
        except Exception:
            pass
        
        # Auto-run PKCS#11 scan once after the GUI is idle (avoid layout races)
        self._pkcs11_scanning = False
        self.root.after_idle(self.browse_pkcs11_auto)
        # Check internet for LTV and TSA
        threading.Thread(target=self._auto_enable_ltv_if_online, daemon=True).start()
        threading.Thread(target=self._auto_enable_tsa_if_online, daemon=True).start()
        
        # İlk önizleme çizimini tetikle
        self.root.after(1000, lambda: self._show_signature_preview(silent=True))
        # Debounce handle for preview auto-refresh (ms timer id)
        self._preview_refresh_after_id = None
        # Debounce handle for signature auto-save
        self._save_sig_after_id = None
        # Tooltip for canvas
        self.canvas_tooltip = None

    def _check_internet_connection(self):
        """Basit bir DNS sorgusu ile internet bağlantısını kontrol eder."""
        try:
            import socket
            # Google DNS (8.8.8.8) port 53 (DNS) control
            # Connection timeout 2 seconds
            sock = socket.create_connection(("8.8.8.8", 53), timeout=2)
            sock.close()
            return True
        except OSError:
            return False

    def _auto_enable_ltv_if_online(self):
        """İnternet varsa LTV'yi otomatik açar, yoksa kapatır."""
        if self._check_internet_connection():
            # Internet available -> Enable LTV
            self.root.after(0, lambda: self.ltv_var.set(True))
            self.root.after(0, lambda: self.log_message("🌐 İnternet algılandı: LTV otomatik açıldı."))
        else:
            # No internet -> Disable LTV to avoid timeouts
            self.root.after(0, lambda: self.ltv_var.set(False))
            self.root.after(0, lambda: self.log_message("⚠️ İnternet yok: LTV kapatıldı."))

    def _auto_enable_tsa_if_online(self):
        """İnternet varsa TSA'yı otomatik açar, yoksa kapatır."""
        if self._check_internet_connection():
            # Internet available -> Enable TSA
            self.root.after(0, lambda: self.tsa_enabled_var.set(True))
            self.root.after(0, lambda: self.log_message("🌐 İnternet algılandı: TSA otomatik açıldı."))
        else:
            # No internet -> Disable TSA to avoid timeouts
            self.root.after(0, lambda: self.tsa_enabled_var.set(False))
            self.root.after(0, lambda: self.log_message("⚠️ İnternet yok: TSA kapatıldı."))

    def build_ui(self):
        # Main container - use GRID for entire layout (no pack/grid mix)
        main_frame = ttk.Frame(self.root, padding=0)
        main_frame.grid(row=0, column=0, sticky='nsew')
        # Configure root to expand
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        # Configure main_frame rows/columns
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=0)  # header doesn't expand
        main_frame.rowconfigure(1, weight=1)  # content area expands
        main_frame.rowconfigure(2, weight=0, minsize=85)  # log fixed height (7 rows)
        main_frame.rowconfigure(3, weight=0)  # footer doesn't expand
        # expose for diagnostics and static analyzers
        self.main_frame = main_frame
        
        # Initialize fonts from constants
        try:
            self._icon_font = (FONT_EMOJI_FAMILY, ICON_FONT_SIZE)
            self._title_font = (FONT_FAMILY, TITLE_FONT_SIZE, "bold")
            self._subtitle_font = (FONT_FAMILY, 10)
        except Exception:
            self._icon_font = ("Segoe UI Emoji", 12)
            self._title_font = ("Segoe UI", 20, "bold")
            self._subtitle_font = ("Segoe UI", 10)
        
        # ===== HEADER =====
        header = ttk.Frame(main_frame, bootstyle="primary", padding=10)
        header.grid(row=0, column=0, sticky='ew')
        
        title_frame = ttk.Frame(header, bootstyle="primary")
        title_frame.pack(side=LEFT)
        
        self.title_icon = BootstrapIcon("shield-check", states=({"color": "white", "size": 28},))
        title_icon_lbl = ttk.Label(title_frame, image=self.title_icon.image, bootstyle="inverse-primary")
        title_icon_lbl.pack(side=LEFT, padx=(0, 5))
        
        title = ttk.Label(
            title_frame,
            text=APP_NAME,
            font=self._title_font,
            bootstyle="inverse-primary"
        )
        title.pack(side=LEFT, padx=5)
        
        version = ttk.Label(
            title_frame,
            text=f"v{APP_VERSION}",
            font=self._subtitle_font,
            bootstyle="inverse-primary"
        )
        version.pack(side=LEFT)
        
        # Header buttons
        btn_frame = ttk.Frame(header, bootstyle="primary")
        btn_frame.pack(side=RIGHT)
        
        self.about_icon = BootstrapIcon(
            "question-circle", 
            "?", 
            states=(
                {"color": "white", "size": 25}, 
                {"color": "white", "size": 30}
            )
        )
        # Label kullanarak butonun etrafındaki beyaz kutu ve padding sorununu kökten çözüyoruz
        about_btn = ttk.Label(
            btn_frame,
            image=self.about_icon.image,
            bootstyle="inverse-primary", # Header bandının koyu mavisiyle tam uyum sağlar
            cursor="hand2"
        )
        about_btn.pack(side=LEFT, padx=5)
        about_btn.bind("<Button-1>", lambda e: self.show_about())
        self.about_icon.attach(about_btn)
        
        # ===== CONTENT AREA =====
        # Scrolled frame for all content
        scroll_frame = ttk.Frame(main_frame)
        scroll_frame.grid(row=1, column=0, sticky='nsew', padx=20, pady=10)
        scroll_frame.columnconfigure(0, weight=1)
        scroll_frame.rowconfigure(0, weight=1)
        
        # Bağımsız dikey dizilim için sütun yapısını güncelliyoruz
        content_frame = ttk.Frame(scroll_frame)
        content_frame.grid(row=0, column=0, sticky='nsew')
        # Sol panel (Yapılandırma) için sabit genişlik (genişlememesini istiyoruz)
        content_frame.columnconfigure(0, weight=0, minsize=330)
        # Sağ panel (İmzalama) genişlemeye izin ver (esnek)
        content_frame.columnconfigure(1, weight=1, minsize=530)
        content_frame.rowconfigure(0, weight=1)

        # Sütunları birbirinden bağımsız hale getiren konteynerler
        left_col = ttk.Frame(content_frame)
        left_col.grid(row=0, column=0, sticky='nsew', padx=(0, 5))
        right_col = ttk.Frame(content_frame)
        right_col.grid(row=0, column=1, sticky='nsew', padx=(5, 0))
        
        # --- LEFT COLUMN (Configuration) ---
        config_tab = ttk.Labelframe(left_col, text="⚙️ Yapılandırma", padding=6, bootstyle="primary")
        config_tab.pack(fill=X, pady=3)
        config_tab.columnconfigure(0, weight=1)
        # store for static analysis / external references
        self.config_tab = config_tab

        # --- Şablon Paneli ---
        template_tab = ttk.Labelframe(left_col, text="🎨 Şablon", padding=0, bootstyle="primary")
        template_tab.pack(fill=BOTH, expand=YES, pady=5)
        template_tab.columnconfigure(0, weight=1)

        self.template_tab = template_tab

        # Gömülü önizleme kanvası
        # UYARI: Canvas boyutu MUTLAKA _draw_preview_on_canvas() içindeki scale parametresiyle eşleşmeli!
        # Eğer scale değeri değişirse, bu boyutlar da güncellenmelidir.
        # 
        # Mevcut ayar: scale=1.35
        # Hesaplama: 
        #   - Genişlik = 210mm (A4 width) * 1.35 = 283.5px ≈ 283px
        #   - Yükseklik = 297mm (A4 height) * 1.35 = 400.95px ≈ 401px
        #
        # NEDEN SABIT BOYUT GEREKLI:
        # Başta canvas'a minsize set edilmezse, _draw_preview_on_canvas() çağrısı yapılana kadar
        # panel boş ve geniş görünüyor (başlangıçta shimmer/reflow yaşanıyor).
        # Sabit boyut belirtmek, canvas'ı layout sisteminde hemen stabilize eder.
        # Canvas wrapper frame for border animation (Opsiyon 3)
        self.canvas_wrapper = ttk.Frame(template_tab)
        self.canvas_wrapper.grid(row=0, column=0, sticky='n', padx=0, pady=0)

        self.embedded_canvas = ttk.Canvas(self.canvas_wrapper, highlightthickness=0, bg="#f0f0f0", width=283, height=401)
        self.embedded_canvas.pack(padx=2, pady=2)  # Padding for border visibility

        # Hover tooltip for drag hint
        self.canvas_tooltip = None

        # OPSIYON 2: Mouse cursor changes to show drag capability
        self.embedded_canvas.bind('<Enter>', self._on_canvas_enter)
        self.embedded_canvas.bind('<Leave>', self._on_canvas_leave)
        self.embedded_canvas.bind('<Motion>', self._on_canvas_motion)  # For tooltip follow
        
        # OPSIYON 3: Canvas border animation (combined with Opsiyon 2)

        # Bind mouse events for drag-drop positioning
        self.embedded_canvas.bind('<Button-1>', self._on_canvas_click)
        self.embedded_canvas.bind('<B1-Motion>', self._on_canvas_drag)
        self.embedded_canvas.bind('<ButtonRelease-1>', self._on_canvas_release)

        self.embedded_canvas.bind('<B1-Motion>', self._on_canvas_drag)
        self.embedded_canvas.bind('<ButtonRelease-1>', self._on_canvas_release)
        
        # PKCS11 Section
        self.create_labeled_frame(config_tab, "🔐 PKCS#11 Modülü", 0)
        
        pkcs11_frame = ttk.Frame(config_tab)
        # Tighter spacing for left panel sections; normalize three-column layout
        pkcs11_frame.grid(row=1, column=0, columnspan=3, sticky=EW, pady=2, padx=4)
        pkcs11_frame.columnconfigure(0, weight=0, minsize=70)
        pkcs11_frame.columnconfigure(1, weight=1)
        pkcs11_frame.columnconfigure(2, weight=0)
        
        ttk.Label(pkcs11_frame, text="DLL Yolu:").grid(row=0, column=0, sticky=W, padx=2, pady=2)
        self.pkcs11_var = ttk.StringVar()
        ttk.Entry(
            pkcs11_frame,
            textvariable=self.pkcs11_var,
            bootstyle="primary"
        ).grid(row=0, column=1, sticky=EW, padx=2, pady=2)
        
        self.browse_icon = BootstrapIcon(
            "folder2",
            "📂",
            (
                {"color": "warning", "name": "folder2"},
                {"color": "white", "name": "folder2-open"},
            ),
        )
        browse_button = ttk.Button(
            pkcs11_frame,
            text="",
            image=self.browse_icon.image,
            bootstyle="warning-outline",
            padding=0,
            command=self.browse_pkcs11
        )
        browse_button.grid(row=0, column=2, sticky=W, padx=2, pady=2)
        self.browse_icon.attach(browse_button)
        

        
        # Token & Certificate Section
        self.create_labeled_frame(config_tab, "🎫 Token Bilgisi", 2)
        
        token_frame = ttk.Frame(config_tab)
        token_frame.grid(row=3, column=0, columnspan=3, sticky=EW, pady=2, padx=4)
        token_frame.columnconfigure(0, weight=0, minsize=70)
        token_frame.columnconfigure(1, weight=1)
        token_frame.columnconfigure(2, weight=0)
        
        ttk.Label(token_frame, text="Token:").grid(row=0, column=0, sticky=W, padx=2, pady=2)
        self._slot_map = {}
        self._token_combo_var = ttk.StringVar(value='(none)')
        from ttkbootstrap import Combobox
        # ensure Combobox is available at module level for static analyzers
        try:
            globals()['Combobox'] = Combobox
        except Exception:
            pass
        self.token_combo = Combobox(token_frame, textvariable=self._token_combo_var, values=['(none)'], state='readonly')
        self.token_combo.grid(row=0, column=1, sticky=EW, padx=2, pady=2)
        self.token_combo.bind('<<ComboboxSelected>>', lambda e: threading.Thread(target=self._on_token_change, args=(self._token_combo_var.get(),), daemon=True).start())
        
        self.refresh_icon = BootstrapIcon("arrow-clockwise", "🔄", ({"color": "warning"}, {"color": "white"}))
        _btn_token_refresh = ttk.Button(
            token_frame,
            text="",
            image=self.refresh_icon.image,
            bootstyle="warning-outline",
            padding=0,
            command=lambda: threading.Thread(target=self._update_tokens_internal, daemon=True).start()
        )
        self.refresh_icon.attach(_btn_token_refresh)
        _btn_token_refresh.grid(row=0, column=2, sticky=W, padx=2, pady=2)
        
        ttk.Label(token_frame, text="SN:").grid(row=1, column=0, sticky=W, padx=2, pady=2)
        self._cert_map = {}
        self._cert_combo_var = ttk.StringVar(value='(none)')
        self.cert_combo = Combobox(token_frame, textvariable=self._cert_combo_var, values=['(none)'], state='readonly')
        self.cert_combo.grid(row=1, column=1, sticky=EW, padx=2, pady=2)
        self.cert_combo.bind('<<ComboboxSelected>>', lambda e: self._update_signature_image_display())
        self.detail_icon = BootstrapIcon("zoom-in", "🔍", ({"color": "warning"}, {"color": "white"}))
        _btn_cert_detail = ttk.Button(
            token_frame,
            text="",
            image=self.detail_icon.image,
            bootstyle="warning-outline",
            padding=0,
            command=self._show_cert_details
        )
        self.detail_icon.attach(_btn_cert_detail)
        _btn_cert_detail.grid(row=1, column=2, sticky=W, padx=2, pady=2)
        
        # Help icon for signing help modal (icon: info color on normal, danger on hover)
        self.help_icon = BootstrapIcon("question-circle", "?", ({"color": "info"}, {"color": "danger"}))
        
        # --- RIGHT COLUMN (Signing) ---
        sign_tab = ttk.Labelframe(right_col, text="✍️ İmzalama", padding=15, bootstyle="primary")
        sign_tab.pack(fill=X, pady=5)
        # store as attribute so type-checkers and nested functions can access it reliably
        self.sign_tab = sign_tab

        # Options Frame (LTV, TSA, Compress PDF, DocMDP)
        options_frame = ttk.Frame(self.sign_tab)
        options_frame.grid(row=6, column=0, columnspan=3, sticky=EW, pady=5, padx=5)
        
        import tkinter as tk # Ensure tk is imported for BooleanVar
        signing_conf = self.config.get('signing', {}) if getattr(self, 'config', None) else {}
        self.default_tsa_url = "http://timestamp.digicert.com"
        
        # LTV Checkbox
        self.ltv_var = tk.BooleanVar(value=bool(signing_conf.get('ltv_enabled', False)))
        self.ltv_check = ttk.Checkbutton(options_frame, text="LTV", variable=self.ltv_var, command=lambda: print("LTV toggled"))
        self.ltv_check.pack(side="left", padx=5)
        
        # Compress PDF Checkbox
        self.compress_pdf_var = tk.BooleanVar(value=False)
        self.compress_check = ttk.Checkbutton(options_frame, text="PDF'i Sıkıştır", variable=self.compress_pdf_var, command=lambda: print("Compress PDF toggled"))
        self.compress_check.pack(side="left", padx=5)

        # TSA (Timestamp Authority) Toggle
        self.tsa_enabled_var = tk.BooleanVar(value=bool(signing_conf.get('tsa_enabled', False)))
        self.tsa_check = ttk.Checkbutton(options_frame, text="TSA", variable=self.tsa_enabled_var, command=lambda: self._save_signing_settings())
        self.tsa_check.pack(side="left", padx=5)

        # DocMDP (certification permissions)
        ttk.Label(options_frame, text="MDP:").pack(side="left")
        self._docmdp_map = {
            "Sadece imza": "signing_only",
            "Form doldurma + imza": "form_fill",
            "Form + yorum + imza": "annotations",
        }
        docmdp_rev = {v: k for k, v in self._docmdp_map.items()}
        default_docmdp = docmdp_rev.get(signing_conf.get('docmdp_mode'), "Sadece imza")
        self.docmdp_var = tk.StringVar(value=default_docmdp)
        self.docmdp_combo = Combobox(options_frame, textvariable=self.docmdp_var, values=list(self._docmdp_map.keys()), state='readonly', width=18)
        self.docmdp_combo.pack(side="left", padx=(4, 0))
        self.docmdp_combo.bind('<<ComboboxSelected>>', lambda e: self._save_signing_settings())
        
        # Help button with icon (far right) - TTK solid light button
        _btn_signing_help = ttk.Button(
            options_frame,
            text="",
            image=self.help_icon.image,
            bootstyle="light",
            padding=0,
            command=self._show_signing_help
        )
        _btn_signing_help.pack(side="left", padx=2)
        self.help_icon.attach(_btn_signing_help)
        CreateToolTip(_btn_signing_help, "İmzalama seçenekleri hakkında bilgi", self.root)
        
        # Persist signing options when changed
        try:
            self.ltv_var.trace_add('write', lambda *a: self._save_signing_settings())
        except Exception:
            pass
        try:
            self.tsa_enabled_var.trace_add('write', lambda *a: self._save_signing_settings())
        except Exception:
            pass
        try:
            self.docmdp_combo.bind('<<ComboboxSelected>>', lambda e: self._save_signing_settings())
        except Exception:
            pass

        # --- İmza Şablonu Paneli (Sağ Alt) ---
        sig_template_tab = ttk.Labelframe(right_col, text="🧾 İmza Şablonu", padding=0, bootstyle="primary")
        sig_template_tab.pack(fill=BOTH, expand=YES, pady=3)
        # Sütunları içeriklerine göre otomatik boyutlandırıyoruz
        # Sol sütun: kontroller, Sağ sütun: görsel
        sig_template_tab.columnconfigure(0, weight=0, minsize=150) # Ayarlar tarafı sabit genişlik
        sig_template_tab.columnconfigure(1, weight=1) # Görsel tarafı kalan alanı doldurur
        sig_template_tab.rowconfigure(0, weight=1)  # Prevent height reflow
        self.sig_template_tab = sig_template_tab
        
        # File Selection
        self.create_labeled_frame(self.sign_tab, "📁 Dosyalar", 0)
        
        file_frame = ttk.Frame(self.sign_tab)
        file_frame.grid(row=1, column=0, columnspan=3, sticky=EW, pady=5, padx=5)
        # Normalize to label / entry / button layout
        file_frame.columnconfigure(0, weight=0, minsize=90)
        file_frame.columnconfigure(1, weight=1)
        file_frame.columnconfigure(2, weight=0, minsize=40)
        
        ttk.Label(file_frame, text="Giriş PDF:").grid(row=0, column=0, sticky=W, padx=5, pady=2)
        self.in_var = ttk.StringVar()
        ttk.Entry(
            file_frame,
            textvariable=self.in_var,
            bootstyle="primary"
        ).grid(row=0, column=1, sticky=EW, padx=5)
        self.in_icon = BootstrapIcon("folder2-open", "📂", ({"color": "warning"}, {"color": "white"}))
        _btn_browse_in = ttk.Button(
            file_frame,
            text="",
            image=self.in_icon.image,
            bootstyle="warning-outline",
            padding=2,
            command=self.browse_in
        )
        self.in_icon.attach(_btn_browse_in)
        _btn_browse_in.grid(row=0, column=2, sticky=W, padx=4)
        
        ttk.Label(file_frame, text="Çıkış PDF:").grid(row=1, column=0, sticky=W, padx=5, pady=2)
        self.out_var = ttk.StringVar()
        ttk.Entry(
            file_frame,
            textvariable=self.out_var,
            bootstyle="primary"
        ).grid(row=1, column=1, sticky=EW, padx=5)
        self.out_icon = BootstrapIcon("folder2-open", "📂", ({"color": "warning"}, {"color": "white"}))
        _btn_browse_out = ttk.Button(
            file_frame,
            text="",
            image=self.out_icon.image,
            bootstyle="warning-outline",
            padding=2,
            command=self.browse_out
        )
        self.out_icon.attach(_btn_browse_out)
        _btn_browse_out.grid(row=1, column=2, sticky=W, padx=4)


        
        # Authentication
        self.create_labeled_frame(self.sign_tab, "🔑 Kimlik Doğrulama", 2)
        
        auth_frame = ttk.Frame(self.sign_tab)
        auth_frame.grid(row=3, column=0, columnspan=3, sticky=EW, pady=5, padx=5)
        # Normalize columns: PIN label, PIN entry, Multi-Sig, Sign button
        auth_frame.columnconfigure(0, weight=0, minsize=60)  # PIN label
        auth_frame.columnconfigure(1, weight=0)  # PIN entry
        auth_frame.columnconfigure(2, weight=0)  # Multi-Sig checkbox
        auth_frame.columnconfigure(3, weight=1)  # Sign button (fills remaining space)
        self.auth_frame = auth_frame  # expose for layout reference
        
        ttk.Label(auth_frame, text="PIN:").grid(row=0, column=0, sticky=W, padx=5, pady=2)
        self.pin_var = ttk.StringVar()
        pin_entry = ttk.Entry(
            auth_frame,
            textvariable=self.pin_var,
            show="•",
            bootstyle="warning",
            width=12
        )
        pin_entry.grid(row=0, column=1, columnspan=1, sticky='w', padx=4)
        # store for layout fixups and tests
        self.pin_entry = pin_entry
        pin_entry.bind('<Return>', lambda e: self.do_sign())
        
        # Multi-Signature Mode Checkbox (moved from options_frame, now right of PIN)
        self.multi_sig_var = tk.BooleanVar(value=False)
        self.multi_sig_check = ttk.Checkbutton(auth_frame, text="Çoklu İmza", variable=self.multi_sig_var, command=lambda: print("Multi-Sig Mode toggled"))
        self.multi_sig_check.grid(row=0, column=2, sticky=W, padx=5, pady=2)
        CreateToolTip(self.multi_sig_check, "Birden fazla kişi aynı belgeyi imzalayacaksa bu seçeneği açın", self.root)

        self.sign_icon = BootstrapIcon("pen-fill", "✍️", ({"color": "white"}, {"color": "white"}))
        self.auth_sign_btn = ttk.Button(
            auth_frame,
            text="İmzala",
            image=self.sign_icon.image,
            compound=LEFT,
            bootstyle="success",
            command=self.do_sign
        )
        self.sign_icon.attach(self.auth_sign_btn)
        self.auth_sign_btn.grid(row=0, column=3, sticky=EW, padx=5)
        
        # Batch sign button
        self.batch_icon = BootstrapIcon("collection-play-fill", "📚", ({"color": "white"}, {"color": "white"}))
        self.batch_sign_btn = ttk.Button(
            auth_frame,
            text="Toplu Belge İmzalama",
            image=self.batch_icon.image,
            compound=LEFT,
            bootstyle="info",
            command=self.do_batch_sign
        )
        self.batch_icon.attach(self.batch_sign_btn)
        self.batch_sign_btn.grid(row=1, column=0, columnspan=4, sticky=EW, padx=5, pady=(5,0))
        CreateToolTip(self.batch_sign_btn, "Birden fazla belgeyi aynı anda imzalamak için bu butonu kullanın", self.root)

        # Optional Fields
        self.create_labeled_frame(self.sign_tab, "📝 İsteğe Bağlı", 4)
        
        optional_frame = ttk.Frame(self.sign_tab)
        optional_frame.grid(row=5, column=0, columnspan=3, sticky=EW, pady=2, padx=5)
        # Two equal-width columns for Reason and Location side-by-side
        optional_frame.columnconfigure(0, weight=0, minsize=50)   # Reason label
        optional_frame.columnconfigure(1, weight=1)                # Reason entry
        optional_frame.columnconfigure(2, weight=0, minsize=35)   # Location label (reduced for less spacing)
        optional_frame.columnconfigure(3, weight=1)                # Location entry
        
        ttk.Label(optional_frame, text="Neden:").grid(row=0, column=0, sticky=W, padx=0, pady=0)
        self.reason_var = ttk.StringVar()
        self.reason_entry = ttk.Entry(optional_frame, textvariable=self.reason_var, bootstyle="secondary")
        self.reason_entry.grid(row=0, column=1, sticky=EW, padx=(0, 4))
        self.reason_placeholder = "Örnek: Sözleşme onayı, belge doğrulama, teslimat onayı"
        # Placeholder for 'Neden' to guide users
        try:
            self._add_entry_placeholder(self.reason_entry, self.reason_placeholder)
        except Exception:
            pass
        
        ttk.Label(optional_frame, text="Yer:").grid(row=0, column=2, sticky=W, padx=0, pady=0)
        self.location_var = ttk.StringVar()
        self.location_entry = ttk.Entry(optional_frame, textvariable=self.location_var, bootstyle="secondary")
        self.location_entry.grid(row=0, column=3, sticky=EW, padx=(0, 4))
        self.location_placeholder = "Örnek: İstanbul, Genel Müdürlük, Online"
        # Placeholder for 'Yer' to guide users
        try:
            self._add_entry_placeholder(self.location_entry, self.location_placeholder)
        except Exception:
            pass

        # Signature placement controls
        sig_frame = ttk.Frame(self.sig_template_tab)
        # Left-align and don't expand - set fixed width to prevent reflow
        sig_frame.grid(row=0, column=0, sticky='nw', pady=5, padx=8)
        # Prevent layout reflow by setting a fixed width constraint
        sig_frame.columnconfigure(0, minsize=130)
        self.sig_frame = sig_frame

        # --- İmza Görseli Bölümü (Sağ tarafa taşındı) ---
        img_container = ttk.Frame(self.sig_template_tab)
        img_container.grid(row=0, column=1, sticky=NSEW, pady=5, padx=8)
        img_container.columnconfigure(0, weight=1)
        # No minsize for rows - let logo and text sit directly adjacent
        img_container.rowconfigure(0, weight=0)
        img_container.rowconfigure(1, weight=0)

        self.sig_img_label = ttk.Label(img_container, text="Görsel aranıyor...", anchor=CENTER)
        self.sig_img_label.grid(row=0, column=0, pady=(0, 0))

        # İmza bilgi metni (PDF'deki görünümün simülasyonu)
        self.sig_info_text_label = ttk.Label(
            img_container, 
            text="", 
            font=("Segoe UI", 8), 
            foreground="black", 
            justify=CENTER,
            anchor=CENTER,
            wraplength=330, # Genişleyen sağ sütuna uyum sağlaması için artırıldı
        )
        self.sig_info_text_label.grid(row=1, column=0, pady=(0, 0))
        # Set initial font of the preview text according to current config
        try:
            self._refresh_sig_info_font()
        except Exception:
            pass

        self.image_icon = BootstrapIcon("image", "🖼️", ({"color": "info"}, {"color": "white"}))
        self.change_img_btn = ttk.Button(
            img_container, 
            text=" Görsel Seç", 
            image=self.image_icon.image,
            compound=LEFT,
            bootstyle="info-outline",
            padding=2,
            command=self._browse_signature_image
        )
        self.change_img_btn.grid(row=2, column=0, pady=3)
        self.image_icon.attach(self.change_img_btn)
        
        # İlk yüklemede görseli göster - daha erken yükle reflow sorununu önlemek için
        self.root.after(100, self._update_signature_image_display)

        sig_conf = self.config.get('signature', {}) if getattr(self, 'config', None) else {}

        # Metin Ayarları: her satır bir `Frame` içinde label + kontrol olacak (tek sütun)
        # Row 0: Logo Gen. - label left, spinbox right
        row0 = ttk.Frame(sig_frame)
        row0.grid(row=0, column=0, sticky=EW, padx=0, pady=3)
        row0.columnconfigure(0, weight=0, minsize=100)  # Label column: sabit genişlik
        row0.columnconfigure(1, weight=0)  # Spinbox: compact
        ttk.Label(row0, text='Logo Gen.').grid(row=0, column=0, sticky=W)
        self.sig_logo_width_var = ttk.Variable(value=sig_conf.get('logo_width_mm', 20.0))
        self.sig_logo_width_entry = ttk.Spinbox(row0, from_=5.0, to=150.0, increment=1, command=self._on_logo_width_spin, textvariable=self.sig_logo_width_var, bootstyle='primary', width="6")
        self.sig_logo_width_entry.grid(row=0, column=1, sticky=E, padx=(4,0))
        self.sig_logo_width_entry.bind('<Up>', self._on_logo_width_arrow)
        self.sig_logo_width_entry.bind('<Down>', self._on_logo_width_arrow)

        # Row 1: Font Boyutu
        row1 = ttk.Frame(sig_frame)
        row1.grid(row=1, column=0, sticky=EW, padx=0, pady=3)
        row1.columnconfigure(0, weight=0, minsize=100)  # Label column: sabit genişlik
        row1.columnconfigure(1, weight=0)  # Spinbox: compact
        ttk.Label(row1, text='Font Boyutu:').grid(row=0, column=0, sticky=W)
        self.sig_width_var = ttk.Variable(value=sig_conf.get('width_mm', 4.5))
        self.sig_width_entry = ttk.Spinbox(row1, from_=1.0, to=50.0, increment=0.5, command=self._on_width_spin, textvariable=self.sig_width_var, bootstyle='primary', width=6)
        self.sig_width_entry.grid(row=0, column=1, sticky=E, padx=(4,0))
        self.sig_width_entry.bind('<Up>', self._on_width_arrow)
        self.sig_width_entry.bind('<Down>', self._on_width_arrow)

        # Row 2: Yatay Hiz.
        row2 = ttk.Frame(sig_frame)
        # Start hidden to prevent layout reflow
        # row2.grid(row=2, column=0, sticky=EW, padx=0, pady=3)
        row2.columnconfigure(0, weight=0, minsize=100)  # Label column: sabit genişlik
        row2.columnconfigure(1, weight=0)  # Spinbox: compact
        self.sig_label_margin_x = ttk.Label(row2, text='Yatay Hiz.')
        self.sig_label_margin_x.grid(row=0, column=0, sticky=W)
        self.sig_margin_x_var = ttk.Variable(value=sig_conf.get('margin_x_mm', sig_conf.get('margin_mm', DEFAULT_SIGNATURE_SETTINGS['margin_mm'])))
        self.sig_margin_x_entry = ttk.Spinbox(row2, from_=-100, to=1000, increment=1, textvariable=self.sig_margin_x_var, bootstyle='primary', width=6)
        self.sig_margin_x_entry.grid(row=0, column=1, sticky=E, padx=(4,0))
        self.sig_margin_x_entry.bind('<Up>', self._on_margin_x_arrow)
        self.sig_margin_x_entry.bind('<Down>', self._on_margin_x_arrow)

        # Row 3: Dikey Hiz.
        row3 = ttk.Frame(sig_frame)
        # Start hidden to prevent layout reflow
        # row3.grid(row=3, column=0, sticky=EW, padx=0, pady=3)
        row3.columnconfigure(0, weight=0, minsize=100)  # Label column: sabit genişlik
        row3.columnconfigure(1, weight=0)  # Spinbox: compact
        self.sig_label_margin_y = ttk.Label(row3, text='Dikey Hiz.')
        self.sig_label_margin_y.grid(row=0, column=0, sticky=W)
        self.sig_margin_y_var = ttk.Variable(value=sig_conf.get('margin_y_mm', sig_conf.get('margin_mm', DEFAULT_SIGNATURE_SETTINGS['margin_mm'])))
        self.sig_margin_y_entry = ttk.Spinbox(row3, from_=-100, to=1000, increment=1, textvariable=self.sig_margin_y_var, bootstyle='primary', width=6)
        self.sig_margin_y_entry.grid(row=0, column=1, sticky=E, padx=(4,0))
        self.sig_margin_y_entry.bind('<Up>', self._on_margin_y_arrow)
        self.sig_margin_y_entry.bind('<Down>', self._on_margin_y_arrow)

        # Row 4: Yer (placement)
        row4 = ttk.Frame(sig_frame)
        # Start hidden to prevent layout reflow
        # row4.grid(row=4, column=0, sticky=EW, padx=0, pady=3)
        row4.columnconfigure(0, weight=0, minsize=100)  # Label column: sabit genişlik
        row4.columnconfigure(1, weight=0)  # Combobox: compact
        self.sig_label_placement = ttk.Label(row4, text='Yer')
        self.sig_label_placement.grid(row=0, column=0, sticky=W)
        placement_vals = [p[1] for p in PLACEMENT_OPTIONS]
        placement_map = {p[1]: p[0] for p in PLACEMENT_OPTIONS}
        self._placement_map = placement_map
        placement_code = sig_conf.get('placement', DEFAULT_SIGNATURE_SETTINGS['placement'])
        placement_display = next((d for c,d in PLACEMENT_OPTIONS if c == placement_code), DEFAULT_SIGNATURE_SETTINGS['placement'])
        self.sig_placement_var = ttk.Variable(value=placement_display)
        try:
            Combobox
        except Exception:
            from ttkbootstrap import Combobox as _CB
            globals()['Combobox'] = _CB
        self.placement_combo = Combobox(row4, textvariable=self.sig_placement_var, values=placement_vals, width=8, state='readonly')
        self.placement_combo.grid(row=0, column=1, sticky=E, padx=(4,0))
        self.placement_combo.bind('<Button-1>', self._on_placement_click, add='+')

        # Hidden rows kept in memory for future use, but not displayed initially
        self.hidden_rows = {'row2': row2, 'row3': row3, 'row4': row4}
        
        # Row 5: Font (label left, combobox right; match spinbox width)
        row5 = ttk.Frame(sig_frame)
        row5.grid(row=5, column=0, sticky=EW, padx=0, pady=3)
        row5.columnconfigure(0, weight=0, minsize=100)  # Label column: sabit genişlik
        row5.columnconfigure(1, weight=0)  # Combobox: compact
        ttk.Label(row5, text='Font:').grid(row=0, column=0, sticky=W)
        font_families = ['Segoe', 'Arial', 'Times', 'Verdana', 'Tahoma', 'Courier']
        self.sig_font_var = ttk.Variable(value=sig_conf.get('font_family', 'Segoe'))
        # Use same visual width as spinboxes
        self.font_combo = Combobox(row5, textvariable=self.sig_font_var, values=font_families, width=8, state='readonly')
        self.font_combo.grid(row=0, column=1, sticky=E, padx=(4,0))
        try:
            self.font_combo.bind('<Button-1>', lambda e: (self.font_combo.focus_set(), self.font_combo.event_generate('<Down>')), add='+')
        except Exception:
            pass

        # Row 6: Stil (label left, combobox right; match spinbox width)
        row6 = ttk.Frame(sig_frame)
        row6.grid(row=6, column=0, sticky=EW, padx=0, pady=3)
        row6.columnconfigure(0, weight=0, minsize=100)  # Label column: sabit genişlik
        row6.columnconfigure(1, weight=0)  # Combobox: compact
        ttk.Label(row6, text='Stil:').grid(row=0, column=0, sticky=W)
        font_styles = ['Normal', 'Bold', 'Italic']
        self.sig_style_var = ttk.Variable(value=sig_conf.get('font_style', 'Bold'))
        self.style_combo = Combobox(row6, textvariable=self.sig_style_var, values=font_styles, width=8, state='readonly')
        self.style_combo.grid(row=0, column=1, sticky=E, padx=(4,0))
        try:
            self.style_combo.bind('<Button-1>', lambda e: (self.style_combo.focus_set(), self.style_combo.event_generate('<Down>')), add='+')
        except Exception:
            pass

        # Open dropdown on click but ensure combobox gets focus first so keyboard events don't affect previously-focused widget
        self.placement_combo.bind('<Button-1>', self._on_placement_click, add='+')

        # Auto-refresh preview and schedule auto-save when signature controls change (trace variables)
        try:
            self.sig_font_var.trace_add('write', lambda *a: (self._refresh_sig_info_font(), self._update_preview() if not getattr(self, '_is_dragging', False) else None, self._schedule_save_signature_settings()))
            self.sig_style_var.trace_add('write', lambda *a: (self._refresh_sig_info_font(), self._update_preview() if not getattr(self, '_is_dragging', False) else None, self._schedule_save_signature_settings()))
            self.sig_width_var.trace_add('write', lambda *a: (self._update_preview() if not getattr(self, '_is_dragging', False) else None, self._schedule_save_signature_settings()))
            self.sig_logo_width_var.trace_add('write', lambda *a: (self._update_preview() if not getattr(self, '_is_dragging', False) else None, self._schedule_save_signature_settings()))
            # For margins we want live updates even during drag; use debounced auto refresh and persist immediately
            self.sig_margin_x_var.trace_add('write', lambda *a: (self._auto_refresh_preview(), self._schedule_save_signature_settings()))
            self.sig_margin_y_var.trace_add('write', lambda *a: (self._auto_refresh_preview(), self._schedule_save_signature_settings()))
            self.sig_placement_var.trace_add('write', lambda *a: (self._on_placement_change() if not getattr(self, '_is_dragging', False) else None, self._schedule_save_signature_settings()))
        except Exception:
            # Older tkinter may not support trace_add; fallback
            try:
                self.sig_width_var.trace('w', lambda *a: (self._auto_refresh_preview(), self._schedule_save_signature_settings()))
                self.sig_logo_width_var.trace('w', lambda *a: (self._auto_refresh_preview(), self._schedule_save_signature_settings()))
                self.sig_margin_x_var.trace('w', lambda *a: (self._auto_refresh_preview(), self._schedule_save_signature_settings()))
                self.sig_margin_y_var.trace('w', lambda *a: (self._auto_refresh_preview(), self._schedule_save_signature_settings()))
                self.sig_placement_var.trace('w', lambda *a: (self._auto_refresh_preview(), self._schedule_save_signature_settings()))
            except Exception:
                pass

        # Select-all-on-click/focus for signature and template entries — improved UX
        try:
            entries = (self.sig_width_entry, self.sig_logo_width_entry, self.sig_margin_x_entry, self.sig_margin_y_entry, self.reason_entry, self.location_entry)
            for e in entries:
                if not e:
                    continue
                # Bind to the entry widget specifically for spinboxes
                if hasattr(e, 'tk'):
                    # For spinbox, bind to the internal entry
                    try:
                        entry_widget = e.tk.call(e._w, 'identify', 'element')
                        if 'entry' in str(entry_widget):
                            e.bind('<FocusIn>', self._select_all_entry, add='+')
                            e.bind('<Button-1>', self._select_all_entry, add='+')
                            e.bind('<FocusOut>', self._clear_entry_selection, add='+')
                        else:
                            e.bind('<FocusIn>', self._select_all_entry, add='+')
                            e.bind('<Button-1>', self._select_all_entry, add='+')
                            e.bind('<FocusOut>', self._clear_entry_selection, add='+')
                    except:
                        e.bind('<FocusIn>', self._select_all_entry, add='+')
                        e.bind('<Button-1>', self._select_all_entry, add='+')
                        e.bind('<FocusOut>', self._clear_entry_selection, add='+')
                else:
                    e.bind('<FocusIn>', self._select_all_entry, add='+')
                    e.bind('<Button-1>', self._select_all_entry, add='+')
                    e.bind('<FocusOut>', self._clear_entry_selection, add='+')
        except Exception:
            pass

        btn_frame_sig = ttk.Frame(sig_frame)
        # Keep this container aligned left and use compact spacing
        btn_frame_sig.grid(row=7, column=0, columnspan=2, sticky=W, padx=0, pady=(6,0))
        # Önizle button with magnifier and Sıfırla button to its right
        self.preview_icon = BootstrapIcon("search", "🔍", ({"color": "info"}, {"color": "white"}))
        _btn_preview = ttk.Button(btn_frame_sig, text=' Önizle', image=self.preview_icon.image, compound=LEFT, bootstyle='info-outline', padding=2, command=lambda: self._show_signature_preview(silent=False))
        self.preview_icon.attach(_btn_preview)
        # Pack without horizontal gap
        _btn_preview.pack(side=LEFT, padx=(0,4))
        self.reset_icon = BootstrapIcon("arrow-counterclockwise", "🔄", ({"color": "warning"}, {"color": "white"}))
        _btn_reset = ttk.Button(btn_frame_sig, text=' Sıfırla', image=self.reset_icon.image, compound=LEFT, bootstyle='warning-outline', padding=2, command=self._reset_signature_settings)
        self.reset_icon.attach(_btn_reset)
        # Pack without horizontal gap
        _btn_reset.pack(side=LEFT, padx=(0,4))

        # Guidance label placed under preview/reset in İmza Şablonu (left panel)
        try:
            hint_frame = ttk.Frame(sig_frame)
            # Place hint only in the left column so it can't force the right column / outer layout to expand
            hint_frame.grid(row=8, column=0, sticky=W, padx=0, pady=(6,2))
            # Prevent the hint from dictating the column width
            hint_frame.columnconfigure(0, weight=0)
            hint_frame.columnconfigure(1, weight=0)
            arrow_lbl = ttk.Label(hint_frame, text='◀', font=(FONT_FAMILY, 11, 'bold'), foreground='red')
            # Left-align the arrow and remove vertical centering
            arrow_lbl.grid(row=0, column=0, sticky=W)
            lbl_drag_hint = ttk.Label(
                hint_frame,
                text='İmza resmini sürükle-bırak ile görünmesini istediğiniz\nkonuma getiriniz',
                font=(FONT_FAMILY, 9, 'italic'),
                foreground='gray',
                wraplength=220,
                width=30,
                anchor=W,
                justify=LEFT
            )
            # No horizontal gap between arrow and text
            lbl_drag_hint.grid(row=0, column=1, sticky=W, padx=0)
        except Exception:
            pass
        
        # CRITICAL: Configure row/column weights for sign_tab so sign_btn is visible
        self.sign_tab.columnconfigure(0, weight=1)
        self.sign_tab.columnconfigure(1, weight=1)
        self.sign_tab.columnconfigure(2, weight=1)  
        
        # ===== LOG PANEL (BOTTOM) =====
        # Log container - a dedicated frame inside main_frame to ensure the
        # log area is resilient to layout changes
        bottom_container = ttk.Frame(self.main_frame)
        bottom_container.grid(row=2, column=0, sticky='ew', padx=20, pady=(0, 5))
        bottom_container.columnconfigure(0, weight=1)
        
        log_frame = ttk.Labelframe(
            bottom_container,
            text="📋 İşlem Günlüğü",
            bootstyle="info",
            padding=5
        )
        log_frame.grid(row=0, column=0, sticky='ew')
        log_frame.rowconfigure(0, weight=0)
        log_frame.columnconfigure(0, weight=1)
        self.log_frame = log_frame

        # Text widget with scrollbar
        log_txt = Text(
            log_frame,
            height=5,
            wrap="word",
            font=("Courier", 9),
            relief="flat",
            background="#f5f5f5",
            foreground="#333",
            insertbackground="#0066cc"
        )
        log_txt.grid(row=0, column=0, sticky='nsew')
        self.log_text = log_txt

        # Configure log filtering
        try:
            self._log_matchers = {
                1: 'Numpad imzalama hatası',
                2: "PKCS#11 DLL seçiliyor",
                3: 'Seçildi:',
                4: 'Seçilen DLL içinde token aranıyor',
                5: '⚠️ Hata:',
                6: 'Token bulundu',
                7: 'Token bulunamadı',
                10: 'Tarama hatası',
                11: 'Tarama tamamlandı:',
                12: 'Auto-selected',
                14: '📂 Giriş',
                15: '➕ Önerilen çıkış',
                16: '📂 Çıkış',
                19: 'Token ve sertifika bulundu',
                20: 'Token bulunamadı',
                21: 'İmzalama işlemi başlatılıyor',
                22: '⚠️ Hata:',
                24: 'DLL yüklenemedi',
                25: 'Token listesi hatası',
                26: 'Token listesi okunamadı',
                27: 'DLL yüklenemedi',
                28: 'Slot arama hatası',
                29: 'Seçilen token bulunamadı',
                30: 'Sertifika okuma hatası',
                31: 'Sertifika okunamadı',
                32: 'İmza ayarları kaydedildi',
                33: 'İmza ayarları kaydedilemedi',
                34: 'İmza ayarları sıfırlandı',
                35: 'Sıfırlama başarısız',
                37: 'Geçersiz imza ayar değeri',
                39: 'İmza resmi okunurken hata',
                41: 'İmza ayarları kaydedilemedi',
                42: 'İptal isteği gönderildi',
                43: 'Token listesi yenilendi'
            }
            self._log_enabled_numbers = set([1,2,3,4,5,6,7,10,11,12,14,15,16,19,20,21,22,24,25,26,27,28,29,30,31,32,33,34,35,37,39,41,42,43])
            self._log_archive = []
        except Exception:
            self._log_matchers = {}
            self._log_enabled_numbers = set()
            self._log_archive = []
        
        v_scrollbar = ttk.Scrollbar(log_frame, orient=VERTICAL, command=log_txt.yview)
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        log_txt.config(yscrollcommand=v_scrollbar.set)
        
        # ===== FOOTER =====
        footer = ttk.Frame(self.main_frame)
        footer.grid(row=3, column=0, sticky='ew')
        footer.columnconfigure(0, weight=1)
        
        footer_label = ttk.Label(
            footer,
            text="© 2026 PDF İmzacı - Dijital İmza Uygulaması",
            font=("Courier", 8),
            foreground="gray"
        )
        footer_label.grid(row=0, column=0, sticky='w', padx=20, pady=5)

    def _clear_entry_selection(self, event):
        """Clear any selection when entry loses focus to avoid lingering highlighted text."""
        try:
            w = event.widget
            w.after(1, lambda: (w.selection_clear(), w.icursor('end')))
        except Exception:
            pass

    def _select_all_entry(self, event):
        """Select all text on FocusIn or click without interfering with click propagation.

        - On FocusIn: select all immediately after focus event.
        - On Button-1: set focus and schedule select-all after a short delay so the click
          can still open comboboxes etc. (do not return 'break').
        This avoids the decrement/double-click bug and ensures a single click selects text.
        """
        try:
            w = event.widget
            # Identify event type reliably (string names may vary across Tkinter versions)
            ev_type = getattr(event, 'type', None)
            # Handle focus in events
            if ev_type == '9' or str(event.type).lower() == 'focusin' or getattr(event, 'type', '') == 'FocusIn':
                w.after(1, lambda: (w.select_range(0, 'end'), w.icursor('end')))
                return
            # Handle Button-1 (mouse click): focus then select shortly after (no event swallowing)
            try:
                w.focus_set()
            except Exception:
                pass
            w.after(1, lambda: (w.select_range(0, 'end'), w.icursor('end')))
        except Exception:
            pass

    def create_labeled_frame(self, parent, text, row):
        """Create a labelled section header with a solid separator (single-row).

        Replaces dashed labelframe decorations with a label on the left and a
        `ttk.Separator` filling the remainder of the row to avoid extra dashed
        lines while keeping the layout grid unchanged.
        """
        hdr = ttk.Frame(parent)
        # Reduced vertical and horizontal spacing for compact layout
        hdr.grid(row=row, column=0, columnspan=3, sticky=EW, pady=(6, 3), padx=2)
        hdr.columnconfigure(1, weight=1)
        lbl = ttk.Label(hdr, text=text, bootstyle="primary")
        lbl.grid(row=0, column=0, sticky=W)
        sep = ttk.Separator(hdr, orient=HORIZONTAL)
        sep.grid(row=0, column=1, sticky='ew', padx=(6,0))
    
    def log_message(self, msg):
        """Write a message to the onscreen log Text widget if available, otherwise print to stdout.
        All messages are archived to `self._log_archive`. If a log filter is configured
        via `_configure_log_filter`, only messages that match the enabled number set
        will be shown in the UI; all are still archived for later inspection.
        """
        try:
            # Ensure archive exists
            if not hasattr(self, '_log_archive'):
                self._log_archive = []
            try:
                self._log_archive.append(msg)
            except Exception:
                pass

            # Helper: determine whether message should be displayed according to filter
            def _should_display(m):
                try:
                    # If no filter configured, display everything
                    if not getattr(self, '_log_enabled_numbers', None):
                        return True
                    # Use matchers map to check if message belongs to an enabled number
                    for num in self._log_enabled_numbers:
                        pat = self._log_matchers.get(num)
                        if pat and pat in m:
                            return True
                    return False
                except Exception:
                    return True

            # Prefer the current attribute name used in build_ui
            target = None
            if hasattr(self, 'log_text') and self.log_text:
                target = self.log_text
            elif hasattr(self, 'log') and self.log:
                target = self.log

            # Only print to console if there is no GUI log target
            if not target:
                try:
                    print(msg)
                except Exception:
                    pass

            if target:
                try:
                    if _should_display(msg):
                        target.insert("end", msg + "\n")
                        target.see("end")
                        return
                    else:
                        # Message filtered out from UI only
                        return
                except Exception:
                    pass
            # No UI target available
            return
        except Exception:
            try:
                print(msg)
            except Exception:
                pass
    
    def browse_pkcs11(self):
        self.log_message("📂 PKCS#11 DLL seçiliyor...")
        cur = self.pkcs11_var.get()
        try:
            curp = Path(cur) if cur else None
            initialdir = str(curp.parent) if curp is not None and curp.parent.exists() else str(Path.cwd())
        except Exception:
            initialdir = str(Path.cwd())
        path = filedialog.askopenfilename(title="PKCS#11 DLL seç", filetypes=[("DLL files", "*.dll"), ("All files","*.*")], initialdir=initialdir)
        if not path:
            return
        self.pkcs11_var.set(path)
        self.log_message(f"Seçildi: {path}")

        def worker(selected):
            self.root.after(0, lambda: self.log_message("🔍 Seçilen DLL içinde token aranıyor..."))
            try:
                has = has_tokens_in_pkcs11_lib(selected)
            except Exception as exc:
                msg = str(exc)
                self.root.after(0, lambda m=msg: self.log_message(f"⚠️ Hata: {m}"))
                has = False
            if has:
                self.root.after(0, lambda: self.log_message("✅ Token bulundu."))
            else:
                self.root.after(0, lambda: self.log_message("❌ Token bulunamadı."))
                # clear combos
                self.root.after(0, lambda: self.token_combo.configure(values=['(none)']))
                self.root.after(0, lambda: self.cert_combo.configure(values=['(none)']))
            try:
                threading.Thread(target=self._update_tokens_internal, daemon=True).start()
            except Exception:
                pass

        threading.Thread(target=worker, args=(path,), daemon=True).start()

    def browse_pkcs11_auto(self):
        if getattr(self, '_pkcs11_scanning', False):
            self.log_message('🔁 PKCS#11 taraması zaten devam ediyor; atlandı.')
            return
        self._pkcs11_scanning = True
        self.log_message("🔍 PKCS#11 DLL'leri otomatik aranıyor...")

        def worker():
            try:
                candidates = find_pkcs11_candidates()
            except Exception as exc:
                candidates = []
                self.root.after(0, lambda m=str(exc): self.log_message(f"⚠️ Tarama hatası: {m}"))

            self.root.after(0, lambda c=len(candidates): self.log_message(f"Tarama tamamlandı: {c} aday bulundu."))

            chosen = None
            for p in candidates:
                try:
                    pstr = str(p)
                    if not is_pkcs11_provider(pstr):
                        self.root.after(0, lambda m=f"❌ {Path(pstr).name}: Geçersiz PKCS#11 sağlayıcı": self.log_message(m))
                        continue
                    if not has_tokens_in_pkcs11_lib(pstr):
                        self.root.after(0, lambda m=f"❌ {Path(pstr).name}: Token bulunamadı": self.log_message(m))
                        continue
                    chosen = pstr
                    self.root.after(0, lambda m=f"✅ {Path(chosen).name}: Geçerli token bulundu!": self.log_message(m))
                    break
                except Exception as e:
                    self.root.after(0, lambda m=f"⚠️ {Path(pstr).name}: Hata - {str(e)}": self.log_message(m))
                    continue

            if chosen:
                self.root.after(0, lambda: self.pkcs11_var.set(chosen))
                self.root.after(0, lambda: self.log_message(f"✅ Auto-selected: {Path(chosen).name}"))
                try:
                    # Pass explicit path to avoid race condition with UI var update
                    threading.Thread(target=self._update_tokens_internal, args=(chosen,), daemon=True).start()
                except Exception:
                    pass
            else:
                self.root.after(0, lambda: self.log_message('❌ No candidate DLLs found. Use "Gözat" to add one manually.'))
                self.root.after(0, lambda: messagebox.showinfo("Sonuç", "DLL bulunamadı. Lütfen elle ekleyin."))
            self._pkcs11_scanning = False

        threading.Thread(target=worker, daemon=True).start()
    def browse_in(self):
        # Determine initial directory: prefer folder in the input textbox, fall back to output folder or CWD
        try:
            cur = self.in_var.get()
            curp = Path(cur) if cur else None
            if curp and curp.exists():
                initialdir = str(curp) if curp.is_dir() else str(curp.parent)
            else:
                out_cur = self.out_var.get()
                outp = Path(out_cur) if out_cur else None
                if outp and outp.exists():
                    initialdir = str(outp.parent if outp.is_file() else outp)
                else:
                    initialdir = str(Path.cwd())
        except Exception:
            initialdir = str(Path.cwd())

        path = filedialog.askopenfilename(title="Giriş PDF seçin", filetypes=[("PDF files","*.pdf"), ("All files","*.*")], initialdir=initialdir)
        if path:
            self.in_var.set(path)
            self.log_message(f"📂 Giriş: {path}")
            # PDF seçildiğinde arka plan şablonunu oluştur
            threading.Thread(target=self._generate_template_from_pdf, args=(path,), daemon=True).start()
            try:
                p = Path(path)
                if not self.out_var.get():
                    default_out = p.with_name(p.stem + '_signed' + p.suffix).as_posix()
                    self.out_var.set(default_out)
                    self.log_message(f"➕ Önerilen çıkış: {default_out}")
            except Exception:
                pass

    def browse_out(self):
        # Prefer the folder already in the output textbox; if missing, try the input textbox's folder; otherwise use CWD
        try:
            cur = self.out_var.get()
            curp = Path(cur) if cur else None
            if curp and cur.exists():
                initialdir = str(curp.parent if curp.is_file() else curp)
            else:
                in_cur = self.in_var.get()
                inp = Path(in_cur) if in_cur else None
                if inp and inp.exists():
                    initialdir = str(inp.parent if inp.is_file() else inp)
                else:
                    initialdir = str(Path.cwd())
        except Exception:
            initialdir = str(Path.cwd())
        path = filedialog.asksaveasfilename(title="Çıkış PDF kaydet",defaultextension=".pdf", filetypes=[("PDF files","*.pdf"), ("All files","*.*")], initialdir=initialdir)
        if path:
            self.out_var.set(path)
            self.log_message(f"📂 Çıkış: {path}")

    def _generate_template_from_pdf(self, pdf_path):
        """Seçilen PDF'in ilk sayfasından dinamik bir önizleme şablonu oluşturur."""
        if fitz is None:
            self.log_message("ℹ️ PDF önizleme için 'PyMuPDF' gerekli: pip install pymupdf")
            return

        try:
            doc = fitz.open(pdf_path)
            if len(doc) > 0:
                page = doc[0]
                # Use 300 DPI consistently with signature image generation to avoid
                # coordinate mismatches on different computers (FIX for signature positioning)
                pix = page.get_pixmap(dpi=300)
                temp_sablon = TEMP_DIR / 'dynamic_sablon.png'
                pix.save(str(temp_sablon))
                self.log_message(f"📄 PDF önizleme şablonu oluşturuldu: {Path(pdf_path).name}")
                # Önizlemeyi tetikle
                self._auto_refresh_preview()
            doc.close()
        except Exception as e:
            self.log_message(f"⚠️ Önizleme şablonu oluşturulamadı: {e}")

    def _show_cert_details(self):
        selected = self._cert_combo_var.get()
        if not selected or selected == '(none)':
            return
            
        cert_obj = self._cert_map.get(selected)
        if not cert_obj:
            return

        # Basic details display
        try:
            from cryptography import x509
            msg = f"Etiket: {selected}\n"
            if isinstance(cert_obj, dict):
                 # Fallback if we stored a dict
                 for k, v in cert_obj.items():
                     msg += f"{k}: {v}\n"
            else:
                 # Assume it's an x509 object or has clear string rep
                 try:
                     subject = cert_obj.subject.rfc4514_string()
                     issuer = cert_obj.issuer.rfc4514_string()
                     serial = cert_obj.serial_number
                     not_before = cert_obj.not_valid_before_utc
                     not_after = cert_obj.not_valid_after_utc
                     
                     msg += f"\nKonu: {subject}"
                     msg += f"\nVeren: {issuer}"
                     msg += f"\nSeri No: {serial}"
                     msg += f"\nGeçerlilik: {not_before} - {not_after}"
                 except Exception:
                     msg += f"\n\nRaw: {str(cert_obj)}"
            
            from tkinter import messagebox
            messagebox.showinfo("Sertifika Detayları", msg)
        except Exception as e:
            self.log_message(f"Detay görüntüleme hatası: {e}")

    def _update_tokens_internal(self, explicit_path=None):
        if explicit_path:
            lib_path = explicit_path
        else:
            # Safely get var from main thread if possible, or assume it's set if called from UI
            try:
                lib_path = self.pkcs11_var.get()
            except RuntimeError:
                # If called from thread without args and var not accessible
                return

        if not lib_path:
            return

        self.root.after(0, lambda: self.log_message("⏳ Token içeriği okunuyor..."))
        
        try:
            from sign_pdf import load_pkcs11_lib, list_certs
            
            # Use a thread to avoid freezing UI
            def worker():
                try:
                    lib = load_pkcs11_lib(lib_path)
                    
                    found_certs = []
                    token_list = []
                    
                    # Reset maps
                    self._cert_map = {}
                    
                    # Iterate slots
                    slots = lib.get_slots(token_present=True)
                    
                    for slot in slots:
                        try:
                            token = slot.get_token()
                            token_info = f"{token.label} ({token.serial})"
                            token_list.append(token_info)
                            
                            # List certs
                            for _, _, label, subject, issuer, serial in list_certs(lib, slot=slot):
                                # Convert subject string to CN only
                                # Typical subject: CN=Name Surname, O=Org, C=TR
                                # We want just "Name Surname"
                                cn_part = subject
                                for part in subject.split(','):
                                    if part.strip().startswith('CN='):
                                        cn_part = part.strip()[3:]
                                        break
                                
                                display_name = cn_part
                                self._cert_map[display_name] = {
                                    'slot_id': slot.slot_id,
                                    'token_label': token.label,
                                    'cert_label': label,
                                    'subject': subject,
                                    'issuer': issuer,
                                    'serial': serial
                                }
                                found_certs.append(display_name)
                                
                        except Exception:
                           pass

                    # Update UI in main thread
                    def update_ui():
                        if token_list:
                            self.token_combo['values'] = token_list
                            self.token_combo.current(0)
                        else:
                            self.token_combo['values'] = ['(bulunamadı)']
                            self.token_combo.set('(bulunamadı)')
                            
                        if found_certs:
                            self.cert_combo['values'] = found_certs
                            self.cert_combo.current(0)
                            self._cert_combo_var.set(found_certs[0])
                            self._update_signature_image_display()
                            self.log_message(f"✅ {len(found_certs)} sertifika listelendi.")
                        else:
                            self.cert_combo['values'] = ['(sertifika yok)']
                            self._cert_combo_var.set('(sertifika yok)')
                            self.log_message("⚠️ Token bulundu ama sertifika okunamadı.")

                    self.root.after(0, update_ui)
                    
                except Exception as e:
                    self.root.after(0, lambda: self.log_message(f"❌ Token okuma hatası: {e}"))

            threading.Thread(target=worker, daemon=True).start()
            
        except Exception as e:
             self.log_message(f"❌ Kütüphane yükleme hatası: {e}")

    def refresh_token(self):
        self.log_message("🔄 Token bilgisi yenileniyor...")
        path = self.pkcs11_var.get()
        if not path:
            self.log_message("❌ PKCS#11 DLL yolu yok; önce seçin veya ara.")
            return

        def worker(selected):
            try:
                has = has_tokens_in_pkcs11_lib(selected)
            except Exception:
                has = False
            if has:
                self.root.after(0, lambda: self.log_message("✅ Token ve sertifika bulundu."))
            else:
                self.root.after(0, lambda: self.log_message("❌ Token bulunamadı."))
                self.root.after(0, lambda: self.token_combo.configure(values=['(none)']))
                self.root.after(0, lambda: self.cert_combo.configure(values=['(none)']))

        threading.Thread(target=worker, args=(path,), daemon=True).start()

    def _show_notification(self, message, duration=2000):
        """Show a transparent orange notification in bottom right corner of GUI window."""
        try:
            # Create notification window
            notif = Toplevel(self.root)
            notif.title("")
            notif.attributes('-alpha', 0.9)  # 90% transparent
            notif.attributes('-topmost', True)
            notif.overrideredirect(True)  # Remove title bar
            
            # Orange background
            notif.config(bg='#FF9800')
            
            # Add label
            label = ttk.Label(
                notif,
                text=message,
                background='#FF9800',
                foreground='white',
                font=('Segoe UI', 10, 'bold'),
                padding=15
            )
            label.pack()
            
            notif.update_idletasks()
            
            # Position at bottom right of GUI window (not screen)
            root_x = self.root.winfo_x()
            root_y = self.root.winfo_y()
            root_width = self.root.winfo_width()
            root_height = self.root.winfo_height()
            
            notif_width = notif.winfo_width()
            notif_height = notif.winfo_height()
            
            # Calculate position relative to GUI window
            x = root_x + root_width - notif_width - 15
            y = root_y + root_height - notif_height - 15
            
            notif.geometry(f'+{x}+{y}')
            
            # Auto close after duration
            notif.after(duration, notif.destroy)
            
        except Exception as e:
            self.log_message(f"⚠️ Bildirim gösterme hatası: {e}")

    def _auto_browse_input(self):
        """Auto-open file dialog and set input file."""
        path = filedialog.askopenfilename(
            title="Giriş PDF seçin",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
            initialdir=str(Path.cwd())
        )
        if path:
            self.in_var.set(path)
            self.log_message(f"📂 Giriş: {path}")
            # PDF seçildiğinde arka plan şablonunu oluştur
            threading.Thread(target=self._generate_template_from_pdf, args=(path,), daemon=True).start()
            try:
                p = Path(path)
                if not self.out_var.get():
                    default_out = p.with_name(p.stem + '_signed' + p.suffix).as_posix()
                    self.out_var.set(default_out)
                    self.log_message(f"➕ Önerilen çıkış: {default_out}")
            except Exception:
                pass

    def do_sign(self):
        # Auto-action: Browse for input if not selected
        if not self.in_var.get():
            self._show_notification("📂 Dosya seçim penceresini açıyorum...")
            self.root.after(500, self._auto_browse_input)
            return
        
        # Auto-action: Focus PIN field if empty
        if not self.pin_var.get().strip():
            self._show_notification("🔐 PIN kodunu girmeniz gerekli")
            try:
                self.pin_entry.focus()
                self.pin_entry.selection_range(0, END)
            except Exception:
                pass
            return
        
        # Auto-action: Trigger output file selection if empty
        if not self.out_var.get():
            self._show_notification("💾 Çıkış dosyasını seçiyorum...")
            path = filedialog.asksaveasfilename(
                title="Çıkış PDF kaydet",
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
                initialdir=str(Path(self.in_var.get()).parent)
            )
            if path:
                self.out_var.set(path)
            return
        
        if not self.pkcs11_var.get():
            self._show_notification("🔑 PKCS#11 DLL seçimi gerekli")
            return

        from types import SimpleNamespace
        args = SimpleNamespace(
            pkcs11_lib=self.pkcs11_var.get(),
            pin=self.pin_var.get(),
            cert_label=None,
            key_label=None,
            in_path=self.in_var.get(),
            out_path=self.out_var.get(),
            reason=self._get_entry_value(self.reason_entry, getattr(self, 'reason_placeholder', None)),
            location=self._get_entry_value(self.location_entry, getattr(self, 'location_placeholder', None)),
            compress_pdf=self.compress_pdf_var.get(),
            ltv_enabled=self.ltv_var.get(),
            tsa_url=self.default_tsa_url if getattr(self, 'tsa_enabled_var', None) and self.tsa_enabled_var.get() else '',
            docmdp_mode=self._docmdp_map.get(self.docmdp_var.get(), 'signing_only') if getattr(self, '_docmdp_map', None) else 'signing_only',
            visual_stamp_path=str(TEMP_DIR / "gui_preview_sig.png"),
            multi_sig_mode=self.multi_sig_var.get()
        )

        self.log_message("✍️ İmzalama işlemi başlatılıyor...")
        try:
            self.auth_sign_btn.configure(state="disabled")
        except Exception:
            pass

        # show progress modal
        self._show_progress_modal()
        try:
            selected_display = self._cert_combo_var.get()
            if selected_display and selected_display != '(none)':
                cert_label = self._cert_map.get(selected_display, {}).get('cert_label')
                if not cert_label:
                    cert_label = selected_display.split('|')[0].strip()
                args.cert_label = cert_label
        except Exception:
            pass

        def worker():
            try:
                from sign_pdf import sign_cmd
                sign_cmd(args, gui_logger=self.log_message)
                try:
                    if args.out_path and os.path.exists(args.out_path):
                        self.log_message(f"📂 Dosya açılıyor: {args.out_path}")
                        try:
                            os.startfile(args.out_path)
                        except Exception as open_err:
                            self.log_message(f"⚠️ Dosya açma hatası: {open_err}")
                            # Fallback to webbrowser
                            try:
                                import webbrowser
                                webbrowser.open(args.out_path)
                            except Exception as wb_err:
                                self.log_message(f"⚠️ Fallback hatası: {wb_err}")
                except Exception as e:
                     self.log_message(f"⚠️ Dosya yolu hatası: {e}")
            except Exception as exc:
                if isinstance(exc, PermissionError):
                    msg = str(exc) or "Çıkış dosyası başka bir program tarafından açık. Lütfen kapatıp tekrar deneyin."
                    self.root.after(0, lambda m=msg: messagebox.showwarning("Dosya açık", m))
                    self.root.after(0, lambda m=msg: self.log_message(f"⚠️ {m}"))
                else:
                    msg = str(exc)
                    self.root.after(0, lambda m=msg: messagebox.showerror("İmza hatası", m))
                    self.root.after(0, lambda m=msg: self.log_message(f"⚠️ Hata: {m}"))
            finally:
                self.root.after(0, lambda: self.auth_sign_btn.configure(state="normal"))
                self.root.after(0, self._close_progress_modal)

        threading.Thread(target=worker, daemon=True).start()

    def do_batch_sign(self):
        """Batch sign all PDF files in the same directory as the selected input file."""
        # Auto-action: Browse for input if not selected
        if not self.in_var.get():
            self._show_notification("📂 Dosya seçim penceresini açıyorum...")
            self.root.after(500, self._auto_browse_input)
            return
        
        # Auto-action: Focus PIN field if empty
        if not self.pin_var.get().strip():
            self._show_notification("🔐 PIN kodunu girmeniz gerekli")
            try:
                self.pin_entry.focus()
                self.pin_entry.selection_range(0, END)
            except Exception:
                pass
            return
        
        if not self.pkcs11_var.get():
            self._show_notification("🔑 PKCS#11 DLL seçimi gerekli")
            return

        # Get directory of selected file
        import pathlib
        selected_file = pathlib.Path(self.in_var.get())
        if not selected_file.exists():
            self._show_notification(f"❌ Dosya bulunamadı: {selected_file.name}")
            return

        directory = selected_file.parent
        
        # Find all PDF files in the directory (including selected file)
        pdf_files = list(directory.glob("*.pdf"))
        # Note: Selected file is included in the batch
        
        if not pdf_files:
            self._show_notification(f"❌ Klasörde PDF dosyası bulunamadı")
            return

        # Show confirmation dialog
        file_list = "\n".join(f"• {f.name}" for f in pdf_files[:10])  # Show first 10 files
        if len(pdf_files) > 10:
            file_list += f"\n... ve {len(pdf_files) - 10} dosya daha"
        
        confirm_msg = f"""Toplu imzalama işlemi başlatılacak.

📁 Klasör: {directory}
📄 Toplam dosya sayısı: {len(pdf_files)}

İmzalanacak dosyalar:
{file_list}

⚠️  Uyarı: Tüm dosyalar aynı imza ayarları ile imzalanacaktır.
Devam etmek istiyor musunuz?"""

        if not messagebox.askyesno("Toplu İmza Onayı", confirm_msg):
            return

        # Get certificate selection
        selected_display = self._cert_combo_var.get()
        cert_label = None
        if selected_display and selected_display != '(none)':
            cert_label = self._cert_map.get(selected_display, {}).get('cert_label')
            if not cert_label:
                cert_label = selected_display.split('|')[0].strip()

        self.log_message(f"📝 Toplu imzalama başlatılıyor... ({len(pdf_files)} dosya)")
        
        # Disable buttons
        try:
            self.auth_sign_btn.configure(state="disabled")
            self.batch_sign_btn.configure(state="disabled")
        except Exception:
            pass

        # Show progress modal
        self._show_progress_modal()

        def batch_worker():
            try:
                from sign_pdf import sign_cmd
                from types import SimpleNamespace
                
                success_count = 0
                error_count = 0
                
                for i, pdf_file in enumerate(pdf_files, 1):
                    try:
                        # Update progress
                        progress_msg = f"İmzalanıyor: {pdf_file.name} ({i}/{len(pdf_files)})"
                        self.root.after(0, lambda m=progress_msg: self.log_message(f"📝 {m}"))
                        
                        # Create output path in "imzalananlar" subdirectory
                        signed_dir = pdf_file.parent / "imzalananlar"
                        signed_dir.mkdir(exist_ok=True)
                        output_file = signed_dir / f"{pdf_file.name}"  # Use original filename
                        
                        # Create args for this file
                        args = SimpleNamespace(
                            pkcs11_lib=self.pkcs11_var.get(),
                            pin=self.pin_var.get(),
                            cert_label=cert_label,
                            key_label=None,
                            in_path=str(pdf_file),
                            out_path=str(output_file),
                            reason=self._get_entry_value(self.reason_entry, getattr(self, 'reason_placeholder', None)),
                            location=self._get_entry_value(self.location_entry, getattr(self, 'location_placeholder', None)),
                            ltv_enabled=self.ltv_var.get(),
                            tsa_url=self.default_tsa_url if getattr(self, 'tsa_enabled_var', None) and self.tsa_enabled_var.get() else '',
                            docmdp_mode=self._docmdp_map.get(self.docmdp_var.get(), 'signing_only') if getattr(self, '_docmdp_map', None) else 'signing_only'
                        )
                        
                        # Sign the file
                        sign_cmd(args, gui_logger=None)  # Don't log individual file messages
                        success_count += 1
                        
                    except Exception as exc:
                        error_msg = f"Hata ({pdf_file.name}): {str(exc)}"
                        self.root.after(0, lambda m=error_msg: self.log_message(f"⚠️ {m}"))
                        error_count += 1
                
                # Final report - Show result window with folder open button
                self.root.after(0, lambda: self._show_batch_sign_result(success_count, error_count, signed_dir))
                
            except Exception as exc:
                msg = str(exc)
                self.root.after(0, lambda m=msg: messagebox.showerror("Toplu İmza Hatası", m))
                self.root.after(0, lambda m=msg: self.log_message(f"⚠️ Genel hata: {m}"))
            finally:
                # Re-enable buttons
                self.root.after(0, lambda: self.auth_sign_btn.configure(state="normal"))
                self.root.after(0, lambda: self.batch_sign_btn.configure(state="normal"))
                self.root.after(0, self._close_progress_modal)

        threading.Thread(target=batch_worker, daemon=True).start()

    def _show_batch_sign_result(self, success_count, error_count, signed_dir):
        """Show batch signing result with professional styling matching flatly theme."""
        try:
            import subprocess
            from tkinter import Frame, Label, Button
            
            # Flatly theme colors
            PRIMARY_BG = "#ecf0f1"      # Light background
            PRIMARY_FG = "#2c3e50"      # Dark text
            SUCCESS_COLOR = "#2ecc71"   # Green
            DANGER_COLOR = "#e74c3c"    # Red
            PRIMARY_BTN = "#3498db"     # Blue
            BORDER_COLOR = "#bdc3c7"    # Light grey
            
            # Create result window using plain Tk instead of ttk to avoid rendering issues
            result_win = Toplevel(self.root)
            result_win.title("Toplu İmza Tamamlandı")
            result_win.geometry("530x310")
            result_win.resizable(False, False)
            result_win.configure(bg=PRIMARY_BG)
            
            # Make window modal
            result_win.transient(self.root)
            result_win.grab_set()
            
            # Center window
            result_win.update_idletasks()
            x = self.root.winfo_x() + (self.root.winfo_width() - 530) // 2
            y = self.root.winfo_y() + (self.root.winfo_height() - 310) // 2
            result_win.geometry(f"530x310+{x}+{y}")
            
            # Main container using plain Tk Frame
            main_frame = Frame(result_win, bg=PRIMARY_BG)
            main_frame.pack(fill=BOTH, expand=True, padx=20, pady=20)
            
            # Header with title
            title_label = Label(
                main_frame,
                text="✅ Toplu İmza Tamamlandı",
                font=("Segoe UI", 13, "bold"),
                bg=PRIMARY_BG,
                fg=SUCCESS_COLOR
            )
            title_label.pack(anchor="w", pady=(0, 15))
            
            # Content frame with border
            content_frame = Frame(main_frame, bg="white", relief="solid", borderwidth=1)
            content_frame.pack(fill=BOTH, expand=True, pady=10)
            
            # Padding inside content
            padding_frame = Frame(content_frame, bg="white")
            padding_frame.pack(fill=BOTH, expand=True, padx=15, pady=15)
            
            # Content label
            content_title = Label(
                padding_frame,
                text="📊 İşlem Sonucu",
                font=("Segoe UI", 10, "bold"),
                bg="white",
                fg=PRIMARY_FG
            )
            content_title.pack(anchor="w", pady=(0, 10))
            
            # Success count
            success_text = f"✓ Başarılı: {success_count} dosya"
            success_label = Label(
                padding_frame,
                text=success_text,
                font=("Segoe UI", 9),
                bg="white",
                fg=SUCCESS_COLOR
            )
            success_label.pack(anchor="w", pady=3)
            
            # Error count (if any)
            if error_count > 0:
                error_text = f"✕ Hatalı: {error_count} dosya"
                error_label = Label(
                    padding_frame,
                    text=error_text,
                    font=("Segoe UI", 9),
                    bg="white",
                    fg=DANGER_COLOR
                )
                error_label.pack(anchor="w", pady=3)
            
            # Location and path (same line)
            location_frame = Frame(padding_frame, bg="white")
            location_frame.pack(anchor="w", pady=(10, 5), fill="x")
            
            location_label = Label(
                location_frame,
                text="📁 Konum:",
                font=("Segoe UI", 9),
                bg="white",
                fg=PRIMARY_FG
            )
            location_label.pack(side="left", padx=(0, 8))
            
            # Path
            path_label = Label(
                location_frame,
                text=str(signed_dir),
                font=("Consolas", 8),
                bg="#f8f9fa",
                fg=PRIMARY_FG,
                wraplength=350,
                justify="left"
            )
            path_label.pack(side="left", fill="x", expand=True)
            
            # Button frame
            button_frame = Frame(main_frame, bg=PRIMARY_BG)
            button_frame.pack(fill="x", pady=(10, 0))
            
            # Open folder button
            def open_folder():
                try:
                    if os.name == 'nt':  # Windows
                        subprocess.Popen(f'explorer "{signed_dir}"')
                    elif os.name == 'posix':  # macOS/Linux
                        subprocess.Popen(['open', str(signed_dir)])
                    result_win.destroy()
                except Exception as e:
                    self.log_message(f"⚠️ Klasör açılırken hata: {e}")
            
            open_btn = Button(
                button_frame,
                text="📁 Klasörü Aç",
                font=("Segoe UI", 9),
                bg=PRIMARY_BTN,
                fg="white",
                activebackground="#2980b9",
                activeforeground="white",
                padx=15,
                pady=6,
                command=open_folder,
                cursor="hand2",
                relief="flat",
                bd=0
            )
            open_btn.pack(side="right", padx=5)
            
            # Close button
            close_btn = Button(
                button_frame,
                text="✓ Kapat",
                font=("Segoe UI", 9),
                bg=SUCCESS_COLOR,
                fg="white",
                activebackground="#27ae60",
                activeforeground="white",
                padx=15,
                pady=6,
                command=result_win.destroy,
                cursor="hand2",
                relief="flat",
                bd=0
            )
            close_btn.pack(side="right", padx=5)
            
            # Log message
            self.log_message(f"✅ Toplu imzalama tamamlandı: {success_count} başarılı")
            
        except Exception as e:
            print(f"ERROR in _show_batch_sign_result: {e}")
            import traceback
            traceback.print_exc()
            self.log_message(f"⚠️ Sonuç penceresini göstermede hata: {e}")
            # Fallback to messagebox
            result_msg = f"Başarıyla imzalanan: {success_count} dosya"
            if error_count > 0:
                result_msg += f"\nHatalı: {error_count} dosya"
            result_msg += f"\n\nKonum: {signed_dir}"
            messagebox.showinfo("Toplu İmza Tamamlandı", result_msg)

    # Token/cert helpers for ttk
    def _update_tokens_from_pkcs11_lib(self):
        path = self.pkcs11_var.get()
        if not path:
            return
        self.root.after(0, lambda: self.log_message(f"🔍 Loading PKCS#11 module: {path}"))
        try:
            lib = load_pkcs11_lib(path)
        except Exception as exc:
            msg = str(exc)
            self.root.after(0, lambda m=msg: self.log_message(f"⚠️ DLL yüklenemedi: {m}"))
            return
        options = []
        slot_map = {}
        attempts = 3
        for attempt in range(attempts):
            try:
                slots = list(lib.get_slots(token_present=True))
                for slot in slots:
                    try:
                        token = slot.get_token()
                    except Exception:
                        token = None
                    label = (getattr(token, 'label', None) or '<unknown>').strip()
                    display = f"{slot.slot_id}: {label}"
                    options.append(display)
                    slot_map[display] = {'slot_id': slot.slot_id, 'serial': getattr(token, 'serial_number', None), 'label': getattr(token, 'label', None)}
                break
            except Exception as exc:
                msg = str(exc)
                if 'initiali' in msg.lower() and attempt + 1 < attempts:
                    self.root.after(0, lambda m=msg: self.log_message(f"⚠️ Token listesi hatası (yeniden deneniyor): {m}"))
                    import time
                    time.sleep(0.45)
                    continue
                self.root.after(0, lambda m=msg: self.log_message(f"⚠️ Token listesi okunamadı: {m}"))
                break
        if not options:
            options = ['(none)']
            slot_map = {}
        def apply():
            try:
                self._slot_map = slot_map
                self.token_combo.configure(values=options)
                last = self.config.get('last_token_display') if getattr(self, 'config', None) else None
                if last and last in options:
                    self._token_combo_var.set(last)
                else:
                    self._token_combo_var.set(options[0])
                self.log_message("✅ Token listesi yenilendi")
                threading.Thread(target=self._on_token_change, args=(self._token_combo_var.get(),), daemon=True).start()
            except Exception:
                pass
        self.root.after(0, apply)

    def _on_token_change(self, value):
        slot_info = self._slot_map.get(value)
        if not slot_info:
            self._cert_map = {}
            self.cert_combo.configure(values=['(none)'])
            self._cert_combo_var.set('(none)')
            return
        try:
            if getattr(self, 'config', None) is not None:
                self.config['last_token_display'] = value
                save_config(self.config)
        except Exception:
            pass
        try:
            threading.Thread(target=self._refresh_certs_for_slot, args=(slot_info,), daemon=True).start()
        except Exception:
            pass

    def _refresh_certs_for_slot(self, slot_info):
        def get_cn_from_subject(subject_str):
            try:
                # Find CN= part, split by comma, and return the value
                parts = subject_str.split(',')
                for part in parts:
                    part = part.strip()
                    if part.upper().startswith('CN='):
                        return part[3:]
                # Fallback if CN is not found but subject exists
                return subject_str.split(',')[0]
            except Exception:
                return subject_str  # Return original string on any error

        try:
            lib = load_pkcs11_lib(self.pkcs11_var.get())
        except Exception as exc:
            msg = str(exc)
            self.root.after(0, lambda m=msg: self.log_message(f"⚠️ DLL yüklenemedi: {m}"))
            return
        certs = []
        cert_map = {}
        # find matching slot in this lib
        target_slot = None
        try:
            for s in lib.get_slots(token_present=True):
                try:
                    t = s.get_token()
                except Exception:
                    t = None
                if s.slot_id == slot_info.get('slot_id'):
                    target_slot = s
                    break
                if t is not None and slot_info.get('serial') and getattr(t, 'serial_number', None) == slot_info.get('serial'):
                    target_slot = s
                    break
                if t is not None and slot_info.get('label') and (t.label or '').strip() == (slot_info.get('label') or '').strip():
                    target_slot = s
                    break
        except Exception as exc:
            msg = str(exc)
            self.root.after(0, lambda m=msg: self.log_message(f"⚠️ Slot arama hatası: {m}"))
            return

        if not target_slot:
            self.root.after(0, lambda: self.log_message('⚠️ Seçilen token bulunamadı (farklı lib örneği).'))
            return

        attempts = 2
        for attempt in range(attempts):
            try:
                for s, token, label, subject, issuer, serial in list_certs(lib, slot=target_slot):
                    display = get_cn_from_subject(subject or '<no subject>')
                    certs.append(display)
                    cert_map[display] = {
                        'cert_label': label,
                        'subject': subject,
                        'issuer': issuer,
                        'token_label': token.label,
                        'slot_id': target_slot.slot_id,
                        'serial': serial
                    }
                break
            except Exception as exc:
                msg = str(exc)
                if 'initiali' in msg.lower() and attempt + 1 < attempts:
                    self.root.after(0, lambda m=msg: self.log_message(f"⚠️ Sertifika okuma hatası (yeniden deneniyor): {m}"))
                    import time
                    time.sleep(0.45)
                    continue
                else:
                    self.root.after(0, lambda m=msg: self.log_message(f"⚠️ Sertifika okunamadı: {m}"))
                    break
        if not certs:
            certs = ['(none)']
            cert_map = {}
        def apply():
            try:
                self._cert_map = cert_map
                self.cert_combo.configure(values=certs)
                last = self.config.get('last_cert_label') if getattr(self, 'config', None) else None
                if last and last in certs:
                    self._cert_combo_var.set(last)
                else:
                    self._cert_combo_var.set(certs[0])
                # Sertifika listesi yenilendiğinde hem label metnini hem de canvas önizlemesini güncelle
                self._show_signature_preview(silent=True)
            except Exception:
                pass
        self.root.after(0, apply)

    def show_cert_details(self):
        sel = self._cert_combo_var.get()
        if not sel or sel == '(none)':
            messagebox.showinfo('Detay', 'Sertifika seçilmedi')
            return
        info = self._cert_map.get(sel)
        if not info:
            messagebox.showinfo('Detay', 'Sertifika bilgisi bulunamadı')
            return
        w = Toplevel(self.root)
        w.title('Sertifika Detayları')
        Label(w, text=f"Label: {sel}").pack(anchor='w', padx=10, pady=5)
        Label(w, text=f"Subject: {info.get('subject')}").pack(anchor='w', padx=10, pady=5)
        Label(w, text=f"Issuer: {info.get('issuer')}").pack(anchor='w', padx=10, pady=5)
        Label(w, text=f"Token: {info.get('token_label')}").pack(anchor='w', padx=10, pady=5)
        Label(w, text=f"Slot: {info.get('slot_id')}").pack(anchor='w', padx=10, pady=5)

    def _save_signature_settings(self):
        """Legacy manual save (kept for compatibility)."""
        try:
            self._auto_save_signature_settings()
            self.log_message('✅ İmza ayarları kaydedildi (manuel)')
        except Exception as exc:
            self.log_message(f'⚠️ İmza ayarları kaydedilemedi: {exc}')

    def _reset_signature_settings(self):
        """Reset signature fields to defaults and save immediately."""
        try:
            defaults = DEFAULT_SIGNATURE_SETTINGS
            # numeric defaults
            self.sig_width_var.set(str(defaults.get('width_mm', 15.0)))
            self.sig_logo_width_var.set(str(defaults.get('logo_width_mm', 20.0)))
            self.sig_margin_x_var.set(str(defaults.get('margin_x_mm', 12.0)))
            self.sig_margin_y_var.set(str(defaults.get('margin_y_mm', 25.0)))
            # placement default display string
            placement_code = defaults.get('placement', DEFAULT_SIGNATURE_SETTINGS['placement'])
            placement_display = next((d for c, d in PLACEMENT_OPTIONS if c == placement_code), placement_code)
            self.sig_placement_var.set(placement_display)
            self.sig_font_var.set(defaults.get('font_family', 'Segoe'))
            self.sig_style_var.set(defaults.get('font_style', 'Bold'))
            # force immediate save and refresh
            try:
                self._auto_save_signature_settings()
            except Exception:
                pass
            # Do not open or refresh the preview when Reset is used (silent reset)
            self.log_message('🔁 İmza ayarları sıfırlandı ve kaydedildi')
        except Exception as exc:
            self.log_message(f'⚠️ Sıfırlama başarısız: {exc}')

    def _show_signature_preview(self, silent=False):
        try:
            from PIL import Image as PILImage
        except ImportError:
            self.log_message("⚠️ Önizleme için 'Pillow' kütüphanesi gerekli. Lütfen kurun: pip install Pillow")
            if not silent:
                messagebox.showerror("Hata", "Önizleme için 'Pillow' kütüphanesi gerekli.")
            return

        # Önizleme penceresi açılmadan önce bilgilerin güncel olduğundan emin olalım
        self._update_signature_image_display()

        # Sol paneldeki gömülü önizlemeyi güncelle (Daha iyi sığması için ölçek 1.18 yapıldı)
        self._draw_preview_on_canvas(self.embedded_canvas, scale=1.35, silent=True)

        # Eğer sessiz moddaysak ve popup zaten açık değilse, burada dur (popup açma)
        if silent and not (hasattr(self, '_preview_win') and self._preview_win.winfo_exists()):
            return

        # --- Constants ---
        A4_W_MM, A4_H_MM = 210, 297
        SCALE = 2.5  # Daha gerçekçi bir görünüm için ölçek artırıldı
        CANVAS_W, CANVAS_H = int(A4_W_MM * SCALE), int(A4_H_MM * SCALE)
        PAGE_COLOR = "white"
        SIG_BOX_COLOR = "red"
        
        # --- Create or focus window ---
        if hasattr(self, '_preview_win') and self._preview_win.winfo_exists():
            try:
                # Keep it on top and lift above main window
                self._preview_win.attributes('-topmost', True)
                self._preview_win.lift()
            except Exception:
                try:
                    self._preview_win.lift()
                except Exception:
                    pass
        else:
            self._preview_win = Toplevel(self.root)
            self._preview_win.title("İmza Önizleme")
            self._preview_win.geometry(f"{CANVAS_W + 80}x{CANVAS_H + 100}")
            self._preview_win.resizable(False, False)
            try:
                # Ensure preview stays above main window
                self._preview_win.attributes('-topmost', True)
                # Mark transient so window manager keeps it above parent
                try:
                    self._preview_win.transient(self.root)
                except Exception:
                    pass
            except Exception:
                pass

            canvas = ttk.Canvas(self._preview_win, width=CANVAS_W, height=CANVAS_H, highlightthickness=0, bg="#f0f0f0")
            canvas.pack(pady=20, padx=20)
            self._preview_canvas = canvas
            
            # Bind mouse events for drag-drop positioning on preview canvas
            canvas.bind('<Button-1>', self._on_canvas_click)
            canvas.bind('<B1-Motion>', self._on_canvas_drag)
            canvas.bind('<ButtonRelease-1>', self._on_canvas_release)
            # Add hover tooltip feedback
            canvas.bind('<Enter>', self._on_canvas_enter)
            canvas.bind('<Leave>', self._on_canvas_leave)
            canvas.bind('<Motion>', self._on_canvas_motion)

            btn_frame = ttk.Frame(self._preview_win)
            btn_frame.pack(pady=15)
            
            self.preview_close_icon = BootstrapIcon("door-closed", "🚪", ({"color": "danger"}, {"color": "white"}))
            _btn_close = ttk.Button(btn_frame, text=" Kapat", image=self.preview_close_icon.image, compound=LEFT, command=self._preview_win.destroy, bootstyle="danger-outline", padding=5)
            self.preview_close_icon.attach(_btn_close)
            _btn_close.pack(side=LEFT, padx=5)

        # Büyük önizleme kanvasını güncelle (eğer pencere açıksa)
        if hasattr(self, '_preview_canvas') and self._preview_canvas:
            self._draw_preview_on_canvas(self._preview_canvas, scale=SCALE, silent=silent)

    def _draw_preview_on_canvas(self, canvas, scale, silent=False):
        """Helper to draw the A4 page and signature preview on a specific canvas.
        
        Args:
            canvas: The tkinter Canvas widget to draw on
            scale: Scale factor for A4 size. 1.0 = 210x297px, 1.35 = 284x401px, etc.
                   Currently set to 1.35 to properly fill the template panel.
            silent: If True, suppress error messages
        """
        if not canvas:
            return
            
        if PILImage is None:
            return

        # --- Constants ---
        A4_W_MM, A4_H_MM = 210, 297
        CANVAS_W = int(A4_W_MM * scale)
        CANVAS_H = int(A4_H_MM * scale)
        PAGE_COLOR = "white"
        SIG_BOX_COLOR = "red"

        # --- Get values from UI ---
        try:
            font_size_mm = float(self.sig_width_var.get() or 0)
            logo_width_mm = float(self.sig_logo_width_var.get() or 0)
            margin_x_mm = float(self.sig_margin_x_var.get() or 0)
            margin_y_mm = float(self.sig_margin_y_var.get() or 0)
            placement_display = self.sig_placement_var.get()
            placement = self._placement_map.get(placement_display, 'top-right')
            font_family = self.sig_font_var.get()
            font_style = self.sig_style_var.get()
        except (ValueError, AttributeError) as e:
            if not silent:
                self.log_message(f"⚠️ Geçersiz imza ayar değeri: {e}")
                messagebox.showerror("Geçersiz Değer", "Lütfen imza ayarları için geçerli sayılar girin.")
            return

        # --- PDF'deki gerçek ölçekleme mantığını simüle et ---
        info_text = self.sig_info_text_label.cget("text")
        signer_lines = info_text.split('\n') if info_text else []
        
        # Get logo path
        try:
            custom_path = self.config.get('signature', {}).get('image_path')
            logo_path = Path(custom_path) if custom_path and Path(custom_path).exists() else resource_path('logo_imza.png')
        except Exception:
            logo_path = resource_path('logo_imza.png')
        
        # Create combined signature image for preview (matches PDF style exactly)
        # Use caching to avoid expensive re-generation when only margins change
        cache_key = (str(logo_path), tuple(signer_lines), font_size_mm, logo_width_mm)
        if getattr(self, '_sig_image_cache_key', None) == cache_key and getattr(self, '_sig_image_cache', None):
            combined_img = self._sig_image_cache
            actual_w_mm = self._sig_actual_w_mm
        else:
            combined_img, actual_w_mm = create_combined_signature_image(
                logo_imza_path=str(logo_path),
                signer_lines=signer_lines,
                font_size_mm=font_size_mm,
                logo_width_mm=logo_width_mm,
                preview_mode=True,
                font_family=font_family,
                font_style=font_style
            )
            if combined_img:
                # Cache the result for future use
                self._sig_image_cache = combined_img
                self._sig_image_cache_key = (str(logo_path), tuple(signer_lines), font_size_mm, logo_width_mm, font_family, font_style)
                # Save a low-res version for reference if needed, but we use the object directly
                try:
                    combined_img.save(TEMP_DIR / "gui_preview_sig.png")
                except Exception:
                    pass

        # Calculate heights for placement math
        # If combined image exists, use its aspect ratio
        if combined_img:
            sig_aspect_ratio = combined_img.height / combined_img.width
        else:
            # Fallback aspect ratio if image creation fails
            sig_aspect_ratio = 0.5 

        actual_block_w_mm = actual_w_mm
        total_sig_height_mm = actual_block_w_mm * sig_aspect_ratio
        total_sig_height_px = int(total_sig_height_mm * scale)

        # --- Calculate position ---
        if placement == 'top-right':
            x_mm = max(4.0, A4_W_MM - margin_x_mm - actual_block_w_mm)
            y_mm = margin_y_mm
        elif placement == 'top-left':
            x_mm = margin_x_mm
            y_mm = margin_y_mm
        elif placement == 'bottom-right':
            x_mm = max(4.0, A4_W_MM - margin_x_mm - actual_block_w_mm)
            y_mm = max(4.0, A4_H_MM - margin_y_mm - total_sig_height_mm)
        elif placement == 'bottom-left':
            x_mm = margin_x_mm
            y_mm = max(4.0, A4_H_MM - margin_y_mm - total_sig_height_mm)
        elif placement == 'center':
            x_mm = (A4_W_MM - actual_block_w_mm) / 2.0 + margin_x_mm
            y_mm = (A4_H_MM - total_sig_height_mm) / 2.0 + margin_y_mm
        else:
            x_mm = max(4.0, A4_W_MM - margin_x_mm - actual_block_w_mm)
            y_mm = margin_y_mm
        
        # --- Draw ---
        canvas.configure(width=CANVAS_W, height=CANVAS_H) # Kanvas boyutunu içeriğe göre güncelle
        canvas.delete("all")

        # Arka plan şablonunu (sablon.pdf) yükle ve çiz
        drawn_bg = False
        try:
            # Önce dinamik oluşturulan PDF sayfasını dene, yoksa sabit sablon.pdf'yi kullan
            dynamic_path = TEMP_DIR / 'dynamic_sablon.png'
            bg_path = dynamic_path if dynamic_path.exists() else resource_path('sablon.pdf')
            
            # Cache background image based on path and scale
            bg_cache_key = (str(bg_path), scale, bg_path.stat().st_mtime if bg_path.exists() else 0)
            if getattr(self, '_bg_image_cache_key', None) == bg_cache_key and getattr(self, '_bg_image_cache', None):
                bg_img = self._bg_image_cache
            elif bg_path.exists():
                if bg_path.suffix.lower() == '.pdf' and fitz:
                    # PDF dosyasını görüntüye dönüştür (PyMuPDF ile)
                    pdf_doc = fitz.open(str(bg_path))
                    if pdf_doc.page_count > 0:
                        page = pdf_doc[0]
                        zoom = 2
                        matrix = fitz.Matrix(zoom, zoom)
                        pix = page.get_pixmap(matrix=matrix)
                        img_data = pix.tobytes("png")
                        from io import BytesIO
                        bg_img = PILImage.open(BytesIO(img_data))
                    else:
                        raise ValueError("PDF boş")
                    pdf_doc.close()
                else:
                    bg_img = PILImage.open(bg_path)
                
                bg_img = bg_img.resize((CANVAS_W, CANVAS_H), PILImage.LANCZOS)
                self._bg_image_cache = bg_img
                self._bg_image_cache_key = bg_cache_key
            else:
                bg_img = None

            if bg_img:
                if canvas == self.embedded_canvas:
                    self._embedded_bg_photo = ImageTk.PhotoImage(bg_img)
                    canvas.create_image(0, 0, anchor=NW, image=self._embedded_bg_photo)
                else:
                    self._preview_bg_photo = ImageTk.PhotoImage(bg_img)
                    canvas.create_image(0, 0, anchor=NW, image=self._preview_bg_photo)
                # Resmin etrafına border çiz
                canvas.create_rectangle(0, 0, CANVAS_W - 1, CANVAS_H - 1, outline="gray")
                drawn_bg = True
        except Exception:
            pass

        if not drawn_bg:
            # Fallback: A4 çerçevesini kendimiz çiziyoruz
            canvas.create_rectangle(0, 0, CANVAS_W - 1, CANVAS_H - 1, fill=PAGE_COLOR, outline="gray")

        x1 = x_mm * scale
        y1 = y_mm * scale
        logo_x1 = x1
        logo_x2 = x1 + actual_block_w_mm * scale
        
        drawn_image = False
        try:
            if combined_img:
                # Use the generated combined image
                img = combined_img.copy()
                sig_w_px = int(round(actual_block_w_mm * scale))
                sig_h_px = int(round(total_sig_height_mm * scale))
                
                if sig_w_px > 0 and sig_h_px > 0:
                    img = img.resize((sig_w_px, sig_h_px), PILImage.LANCZOS)
                    if canvas == self.embedded_canvas:
                        self._embedded_sig_photo = ImageTk.PhotoImage(img)
                        canvas.create_image(logo_x1, y1, anchor=NW, image=self._embedded_sig_photo, tags="logo")
                    else:
                        self._preview_sig_photo = ImageTk.PhotoImage(img)
                        canvas.create_image(logo_x1, y1, anchor=NW, image=self._preview_sig_photo, tags="logo")
                    drawn_image = True
            elif logo_path and logo_path.exists():
                # Fallback to just logo if combined failed
                img = PILImage.open(logo_path)
                logo_w_px = int(round(logo_width_mm * scale))
                logo_h_px = int(round(logo_width_mm * (img.height/img.width) * scale))
                if logo_w_px > 0 and logo_h_px > 0:
                    img = img.resize((logo_w_px, logo_h_px), PILImage.LANCZOS)
                    # center logo in block
                    lx = x1 + (actual_block_w_mm - logo_width_mm) / 2 * scale
                    if canvas == self.embedded_canvas:
                        self._embedded_sig_photo = ImageTk.PhotoImage(img)
                        canvas.create_image(lx, y1, anchor=NW, image=self._embedded_sig_photo, tags="logo")
                    else:
                        self._preview_sig_photo = ImageTk.PhotoImage(img)
                        canvas.create_image(lx, y1, anchor=NW, image=self._preview_sig_photo, tags="logo")
                    drawn_image = True
        except Exception as e:
            try:
                self.log_message(f"⚠️ İmza önizleme hatası: {e}")
            except Exception:
                pass

        # Always draw the rectangle for drag purposes
        canvas.create_rectangle(logo_x1, y1, logo_x2, y1 + total_sig_height_px, outline="", tags="logo")
        # For very small rectangles, add an invisible larger hit-area to ease mouse targeting (tagged separately)
        try:
            min_hit_h = 8  # pixels - only for interaction convenience
            if total_sig_height_px < min_hit_h:
                pad = (min_hit_h - total_sig_height_px)
                hit_top = y1 - (pad/2)
                hit_bottom = y1 + total_sig_height_px + (pad/2)
                hit_rect = canvas.create_rectangle(logo_x1 - 2, hit_top, logo_x2 + 2, hit_bottom, outline="", tags=("logo_hit",))
                # Ensure the hit rect is below visible items so it doesn't obscure visuals
                try:
                    canvas.tag_lower(hit_rect)
                except Exception:
                    pass
        except Exception:
            pass

        if not drawn_image:
            # Fill rectangle if no image
            canvas.itemconfig(canvas.find_withtag("logo")[-1], fill=SIG_BOX_COLOR, stipple="gray50")
            text_cy = y1 + (total_sig_height_px / 2)
            canvas.create_text((logo_x1 + logo_x2) / 2, text_cy, text="İmza", fill="white", font=("Segoe UI", int(10 * (scale/2.5)), "bold"), tags="logo")
            
        # No longer drawing info_text separately since it's in the combined image
        # (Removed separate canvas.create_text call for info_text)

    def _auto_refresh_preview(self, *args):
        """Debounced auto-refresh for the preview window.

        Schedules a single redraw 250ms after the last change. This avoids
        reacting to transient empty values while the user is editing.
        """
        try:
            # Cancel previously scheduled refresh
            try:
                if getattr(self, '_preview_refresh_after_id', None):
                    self.root.after_cancel(self._preview_refresh_after_id)
            except Exception:
                pass
            # If the entry is currently empty (user clicked to replace), postpone scheduling until it has some content
            try:
                v = self.sig_width_var.get()
                if v == "":
                    # schedule a re-check later; skip immediate refresh
                    self._preview_refresh_after_id = self.root.after(250, lambda: self._auto_refresh_preview())
                    return
            except Exception:
                pass
            # Schedule a new refresh after 250ms
            self._preview_refresh_after_id = self.root.after(250, lambda: self._show_signature_preview(silent=True))
        except Exception:
            pass

    def _update_preview(self):
        """Simple wrapper for silent preview refresh."""
        self._show_signature_preview(silent=True)

    def _on_width_spin(self):
        self._auto_refresh_preview()
        self._schedule_save_signature_settings()

    def _on_width_arrow(self, event):
        try:
            val = float(self.sig_width_var.get() or 0)
            if event.keysym == 'Up':
                val += 0.5
            elif event.keysym == 'Down':
                val -= 0.5
            self.sig_width_var.set(f"{max(0.5, val):.1f}")
            self._on_width_spin()
        except Exception:
            pass

    def _on_logo_width_spin(self):
        self._auto_refresh_preview()
        self._schedule_save_signature_settings()

    def _on_logo_width_arrow(self, event):
        try:
            val = float(self.sig_logo_width_var.get() or 0)
            if event.keysym == 'Up':
                val += 1
            elif event.keysym == 'Down':
                val -= 1
            self.sig_logo_width_var.set(f"{max(0.1, val):.2f}")
            self._on_logo_width_spin()
        except Exception:
            pass

    def _on_margin_x_arrow(self, event):
        try:
            val = float(self.sig_margin_x_var.get() or 0)
            if event.keysym == 'Up':
                val += 1
            elif event.keysym == 'Down':
                val -= 1
            self.sig_margin_x_var.set(f"{val:.2f}")
            self._auto_refresh_preview()
            self._schedule_save_signature_settings()
        except Exception:
            pass

    def _on_margin_y_arrow(self, event):
        try:
            val = float(self.sig_margin_y_var.get() or 0)
            if event.keysym == 'Up':
                val += 1
            elif event.keysym == 'Down':
                val -= 1
            self.sig_margin_y_var.set(f"{val:.2f}")
            self._auto_refresh_preview()
            self._schedule_save_signature_settings()
        except Exception:
            pass

    def _on_placement_click(self, event):
        try:
            event.widget.focus_set()
            event.widget.event_generate('<Down>')
        except Exception:
            pass

    def _on_canvas_click(self, event):
        """Start drag operation on the signature box."""
        try:
            # Check if click is near the signature (tagged with "logo" or "logo_hit")
            item = event.widget.find_closest(event.x, event.y)
            tags = event.widget.gettags(item)
            if "logo" in tags or "logo_hit" in tags:
                self._is_dragging = True
                self._drag_start_x = event.x
                self._drag_start_y = event.y
                self._drag_last_x = event.x
                self._drag_last_y = event.y
                # Store original margins to calculate delta
                self._drag_orig_margin_x = float(self.sig_margin_x_var.get() or 0)
                self._drag_orig_margin_y = float(self.sig_margin_y_var.get() or 0)
                event.widget.config(cursor="fleur")
                # Hide tooltips when dragging starts
                self._hide_canvas_tooltip()
        except Exception:
            pass

    def _on_canvas_drag(self, event):
        """Update signature margins during drag without full redraw for better performance."""
        if not getattr(self, '_is_dragging', False):
            return
        try:
            # Move items on canvas immediately for smooth feedback
            dx_total = event.x - self._drag_start_x
            dy_total = event.y - self._drag_start_y
            
            move_x = event.x - self._drag_last_x
            move_y = event.y - self._drag_last_y
            
            event.widget.move("logo", move_x, move_y)
            self._drag_last_x = event.x
            self._drag_last_y = event.y

            # Convert pixel delta to mm (approximate using scale)
            # Find scale by looking at current canvas width vs A4 width
            canvas_w = event.widget.winfo_width()
            scale = canvas_w / 210.0 if canvas_w > 0 else 1.18
            
            dx_mm = dx_total / scale
            dy_mm = dy_total / scale
            
            # Update margins based on placement logic
            placement_display = self.sig_placement_var.get()
            placement = self._placement_map.get(placement_display, 'top-right')
            
            new_mx = self._drag_orig_margin_x
            new_my = self._drag_orig_margin_y
            
            if placement == 'top-right':
                new_mx -= dx_mm
                new_my += dy_mm
            elif placement == 'top-left':
                new_mx += dx_mm
                new_my += dy_mm
            elif placement == 'bottom-right':
                new_mx -= dx_mm
                new_my -= dy_mm
            elif placement == 'bottom-left':
                new_mx += dx_mm
                new_my -= dy_mm
            elif placement == 'center':
                new_mx += dx_mm
                new_my += dy_mm
                
            # Update variables (this triggers debounced refresh which we skip during dragging)
            self.sig_margin_x_var.set(f"{new_mx:.2f}")
            self.sig_margin_y_var.set(f"{new_my:.2f}")
            
            # Do NOT call _show_signature_preview here; canvas is already updated via .move()
        except Exception:
            pass

    def _on_canvas_release(self, event):
        """End drag operation and save settings."""
        if getattr(self, '_is_dragging', False):
            self._is_dragging = False
            event.widget.config(cursor="")
            # Full sync and refresh to ensure everything is perfect
            self._show_signature_preview(silent=True)
            self._schedule_save_signature_settings()

    def _schedule_save_signature_settings(self):
        """Debounced schedule to persist signature settings to config."""
        try:
            try:
                if getattr(self, '_save_sig_after_id', None):
                    self.root.after_cancel(self._save_sig_after_id)
            except Exception:
                pass
            # schedule actual save after 350ms
            self._save_sig_after_id = self.root.after(350, self._auto_save_signature_settings)
        except Exception:
            pass

    def _auto_save_signature_settings(self):
        """Persist validated signature settings to config automatically."""
        try:
            # Validate numbers
            try:
                w = float(self.sig_width_var.get())
                lw = float(self.sig_logo_width_var.get())
                mx = float(self.sig_margin_x_var.get())
                my = float(self.sig_margin_y_var.get())
            except Exception:
                return  # don't save invalid entries

            # placement code
            placement_display = self.sig_placement_var.get()
            placement_code = self._placement_map.get(placement_display)
            if not placement_code:
                # fallback to default
                placement_code = DEFAULT_SIGNATURE_SETTINGS.get('placement')

            # write config
            try:
                if getattr(self, 'config', None) is None:
                    self.config = {}
                self.config.setdefault('signature', {})['width_mm'] = w
                self.config['signature']['logo_width_mm'] = lw
                self.config['signature']['margin_x_mm'] = mx
                self.config['signature']['margin_y_mm'] = my
                self.config['signature']['placement'] = placement_code
                self.config['signature']['font_family'] = self.sig_font_var.get()
                self.config['signature']['font_style'] = self.sig_style_var.get()
                save_config(self.config)
            except Exception as e:
                self.log_message(f'⚠️ İmza ayarları kaydedilemedi: {e}')
        except Exception:
            pass

    def _save_signing_settings(self):
        """Persist signing options (LTV, TSA enabled, DocMDP) to config."""
        try:
            if getattr(self, 'config', None) is None:
                self.config = {}
            self.config.setdefault('signing', {})['ltv_enabled'] = bool(self.ltv_var.get())
            self.config['signing']['tsa_enabled'] = bool(self.tsa_enabled_var.get())
            try:
                display = self.docmdp_var.get()
                mode = self._docmdp_map.get(display, 'signing_only')
            except Exception:
                mode = 'signing_only'
            self.config['signing']['docmdp_mode'] = mode
            save_config(self.config)
        except Exception:
            pass

    def _on_placement_change(self):
        """Handle placement change - reset margins to 0 for center placement."""
        try:
            placement_display = self.sig_placement_var.get()
            placement_code = self._placement_map.get(placement_display)
            if placement_code == 'center':
                # Reset margins to 0 for center placement
                self.sig_margin_x_var.set("0.00")
                self.sig_margin_y_var.set("0.00")
                self.log_message("Orta yer seçildi, margin'ler 0'a sıfırlandı")
            # Always update preview
            self._update_preview()
        except Exception as e:
            self.log_message(f"Yer değiştirme hatası: {e}")
            self._update_preview()

    def _add_entry_placeholder(self, entry, text):
        """Add a simple placeholder to a ttk.Entry.

        This inserts `text` when the entry is empty and greys it out. When the
        user focuses the entry, the placeholder is removed. When focus leaves
        and the entry is empty, the placeholder is restored.
        """
        try:
            # Colors - try to be compatible with ttk
            normal_fg = entry.cget('foreground') if 'foreground' in entry.keys() else 'black'
        except Exception:
            normal_fg = 'black'
        placeholder_fg = 'gray50'

        def _on_focus_in(e):
            try:
                if entry.get() == text:
                    entry.delete(0, 'end')
                    entry.config(foreground=normal_fg)
            except Exception:
                pass

        def _on_focus_out(e):
            try:
                if entry.get().strip() == '':
                    entry.insert(0, text)
                    entry.config(foreground=placeholder_fg)
            except Exception:
                pass

        # Initialize placeholder if empty
        try:
            if not entry.get().strip():
                entry.insert(0, text)
                entry.config(foreground=placeholder_fg)
        except Exception:
            pass

        # Bind events
        try:
            entry.bind('<FocusIn>', _on_focus_in)
            entry.bind('<FocusOut>', _on_focus_out)
        except Exception:
            pass

    def _get_entry_value(self, entry, placeholder_text=None):
        """Return entry value unless it is empty or equals the placeholder."""
        try:
            val = entry.get()
        except Exception:
            return ''
        if not val:
            return ''
        trimmed = val.strip()
        if not trimmed:
            return ''
        if placeholder_text and trimmed == placeholder_text:
            return ''
        return trimmed

    def _show_progress_modal(self):
        try:
            win = Toplevel(self.root)
            win.title('İmzalama İşlemi')
            win.geometry('420x140')
            win.resizable(False, False)
            
            # Center the progress window on the main window
            win.update_idletasks()
            main_x = self.root.winfo_x()
            main_y = self.root.winfo_y()
            main_w = self.root.winfo_width()
            main_h = self.root.winfo_height()
            win_w = win.winfo_width()
            win_h = win.winfo_height()
            x = main_x + (main_w - win_w) // 2
            y = main_y + (main_h - win_h) // 2
            win.geometry(f'+{x}+{y}')
            
            win.grab_set()
            self._progress_win = win
            lbl = Label(win, text='⏳ PDF imzalanıyor... Lütfen bekleyin', font=('Arial', 11))
            lbl.pack(pady=10)
            try:
                from tkinter import ttk as _ttk
                pb = _ttk.Progressbar(win, mode='indeterminate', length=300)
                pb.pack(pady=10)
                pb.start(10)
                self._progress_bar = pb
            except Exception:
                pass
            ttk.Button(win, text='İptal', bootstyle='danger-outline', command=self._request_cancel).pack(pady=5)
        except Exception:
            pass

    def _request_cancel(self):
        try:
            self._sign_cancel_requested = True
            self.log_message('⚠️ İptal isteği gönderildi; işlem iptal edilemeyebilir.')
        except Exception:
            pass

    def _close_progress_modal(self):
        try:
            if hasattr(self, '_progress_bar') and self._progress_bar:
                try:
                    self._progress_bar.stop()
                except Exception:
                    pass
            if hasattr(self, '_progress_win') and self._progress_win:
                try:
                    self._progress_win.grab_release()
                except Exception:
                    pass
                try:
                    self._progress_win.destroy()
                except Exception:
                    pass
            self._progress_win = None
            self._progress_bar = None
        except Exception:
            pass

    def _on_close(self):
        """Handler for window close: persist signature settings then close."""
        try:
            self._auto_save_signature_settings()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            try:
                self.root.quit()
            except Exception:
                pass

    def show_about(self):
        # Create modern about dialog
        about = ttk.Toplevel(self.root)
        about.title("Hakkında")
        about.geometry("450x380")
        about.resizable(False, False)
        
        # Center window on parent
        about.transient(self.root)
        about.grab_set()
        self.root.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 450) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 380) // 2
        about.geometry(f"450x380+{x}+{y}")
        
        frame = ttk.Frame(about, padding=30)
        frame.pack(fill=BOTH, expand=YES)
        
        ttk.Label(
            frame,
            text="📄 PDF İmzacı",
            font=("Segoe UI", 26, "bold"),
            bootstyle="primary"
        ).pack(pady=15)
        
        ttk.Label(
            frame,
            text="Versiyon 2.3",
            font=("Segoe UI", 11),
            bootstyle="secondary"
        ).pack(pady=3)
        
        ttk.Label(
            frame,
            text="© 2026 by Selim Sağol",
            font=("Segoe UI", 10),
            bootstyle="secondary"
        ).pack(pady=15)
        
        # Email section
        ttk.Label(
            frame,
            text="İletişim:",
            font=("Segoe UI", 10, "bold")
        ).pack(pady=(10, 3))
        
        email_frame = ttk.Frame(frame)
        email_frame.pack(pady=5)
        
        ttk.Label(
            email_frame,
            text="✉️",
            font=("Segoe UI", 12)
        ).pack(side=LEFT, padx=5)
        
        # Clickable email label
        email_label = ttk.Label(
            email_frame,
            text="selimsagol@hotmail.com",
            font=("Segoe UI", 10),
            bootstyle="info"
        )
        email_label.pack(side=LEFT)
        
        # Make email label clickable and hoverable
        def on_email_enter(e):
            email_label.config(cursor="hand2")
        
        def on_email_leave(e):
            email_label.config(cursor="arrow")
        
        def on_email_click(e):
            webbrowser.open("mailto:selimsagol@hotmail.com")
        
        email_label.bind("<Enter>", on_email_enter)
        email_label.bind("<Leave>", on_email_leave)
        email_label.bind("<Button-1>", on_email_click)
        
        # Buttons frame
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=(15, 0))
        
        # Help button
        self.about_help_icon = BootstrapIcon("question-circle", "❓", ({"color": "info"}, {"color": "white"}))
        help_btn = ttk.Button(
            btn_frame,
            text=" Yardım Kılavuzu",
            image=self.about_help_icon.image,
            compound=LEFT,
            bootstyle="info-outline",
            command=self._open_help_guide,
            padding=2
        )
        help_btn.pack(side=LEFT, padx=5)
        self.about_help_icon.attach(help_btn)
        
        # Close button
        self.about_close_icon = BootstrapIcon("x-circle", "✖", ({"color": "secondary"}, {"color": "white"}))
        about_close_btn = ttk.Button(
            btn_frame,
            text=" Kapat",
            image=self.about_close_icon.image,
            compound=LEFT,
            bootstyle="secondary-outline",
            command=about.destroy,
            padding=2
        )
        about_close_btn.pack(side=LEFT, padx=5)
        self.about_close_icon.attach(about_close_btn)

    def _open_help_guide(self):
        """Open help guide in a new window (single instance)."""
        try:
            from pathlib import Path
            
            # If help window already exists, bring it to front
            if hasattr(self, '_help_win') and self._help_win.winfo_exists():
                self._help_win.lift()
                self._help_win.focus()
                return
            
            guide_path = Path(__file__).parent / "KULLANIM_KILAVUZU.md"
            
            if not guide_path.exists():
                messagebox.showerror(
                    "Dosya Bulunamadı",
                    f"Yardım kılavuzu bulunamadı: {guide_path}"
                )
                return
            
            # Create help window
            help_win = Toplevel(self.root)
            help_win.title("Yardım Kılavuzu - PDF İmzacı")
            help_win.geometry("900x780")
            self._help_win = help_win
            
            # Make window modal
            help_win.transient(self.root)
            help_win.grab_set()
            
            # Center window
            help_win.update_idletasks()
            x = self.root.winfo_x() + (self.root.winfo_width() - 900) // 2
            y = self.root.winfo_y() + (self.root.winfo_height() - 780) // 2
            help_win.geometry(f"900x780+{x}+{y}")
            
            # Create frame with scrollbar
            main_frame = ttk.Frame(help_win)
            main_frame.pack(fill=BOTH, expand=YES, padx=8, pady=8)
            
            # Text widget with scrollbar
            text_frame = ttk.Frame(main_frame)
            text_frame.pack(fill=BOTH, expand=YES)
            
            # Use tkinter Scrollbar instead of ttk for better drag support
            from tkinter import Scrollbar as TkScrollbar
            scrollbar = TkScrollbar(text_frame)
            scrollbar.pack(side=RIGHT, fill=Y)
            
            text_widget = Text(
                text_frame,
                wrap=WORD,
                yscrollcommand=scrollbar.set,
                font=("Consolas", 10),
                bg="white",
                fg="#333333",
                padx=15,
                pady=10,
                height=40,
                width=120
            )
            text_widget.pack(side=LEFT, fill=BOTH, expand=YES)
            scrollbar.config(command=text_widget.yview)
            
            # Mouse wheel scroll support
            def _on_mousewheel(event):
                if event.delta > 0:
                    text_widget.yview_scroll(-3, "units")
                else:
                    text_widget.yview_scroll(3, "units")
            
            text_widget.bind("<MouseWheel>", _on_mousewheel)
            text_widget.bind("<Button-4>", lambda e: text_widget.yview_scroll(-3, "units"))
            text_widget.bind("<Button-5>", lambda e: text_widget.yview_scroll(3, "units"))
            
            # Read and display guide content
            with open(guide_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            text_widget.insert("1.0", content)
            text_widget.config(state="disabled")  # Read-only
            
            # Footer frame with contact info
            footer_frame = ttk.Frame(main_frame)
            footer_frame.pack(pady=2, fill=X)
            
            ttk.Label(
                footer_frame,
                text="Sorularınız için: ",
                font=("Segoe UI", 9)
            ).pack(side=LEFT, padx=5)
            
            # Clickable email in help window
            help_email_label = ttk.Label(
                footer_frame,
                text="selimsagol@hotmail.com",
                font=("Segoe UI", 9),
                bootstyle="info"
            )
            help_email_label.pack(side=LEFT)
            
            def on_help_email_enter(e):
                help_email_label.config(cursor="hand2")
            
            def on_help_email_leave(e):
                help_email_label.config(cursor="arrow")
            
            def on_help_email_click(e):
                import webbrowser
                webbrowser.open("mailto:selimsagol@hotmail.com")
            
            help_email_label.bind("<Enter>", on_help_email_enter)
            help_email_label.bind("<Leave>", on_help_email_leave)
            help_email_label.bind("<Button-1>", on_help_email_click)
            
            # Close button frame
            btn_frame = ttk.Frame(main_frame)
            btn_frame.pack(pady=5, fill=X)
            
            # Button container for centering
            button_container = ttk.Frame(btn_frame)
            button_container.pack(anchor=CENTER)
            
            close_icon = BootstrapIcon("x-circle", "✖", ({"color": "secondary"}, {"color": "white"}))
            close_btn = ttk.Button(
                button_container,
                text=" Kapat",
                image=close_icon.image,
                compound=LEFT,
                bootstyle="secondary-outline",
                command=help_win.destroy,
                padding=2
            )
            close_btn.pack()
            close_icon.attach(close_btn)
            
        except Exception as e:
            messagebox.showerror(
                "Hata",
                f"Yardım kılavuzu açılırken hata oluştu:\n{str(e)}"
            )

    def _show_signing_help(self):
        """Show comprehensive modal explaining all signing options (LTV, TSA, DocMDP)."""
        try:
            title = "İmzalama Seçenekleri"
            body = (
                "LTV (Long-Term Validation):\n"
                "İmza anındaki doğrulama verilerini (OCSP/CRL gibi) PDF içine gömerek,\n"
                "belgenin yıllar sonra da doğrulanabilmesini sağlar. Resmi/uzun süreli belgeler için ON yapın.\n\n"
                "TSA (Timestamp Authority / Zaman Damgası):\n"
                "İmza zamanını güvenilir bir zaman kaynağı ile damgalar. Müşteri belgeler için\n"
                "E-İmza Kanunu gereği imza zamanının güvenilir olması gerekir. İnternet varsa\n"
                "TSA otomatik açılır. Varsayılan URL: timestamp.digicert.com\n\n"
                "MDP (Certification Permissions / Doküman Değişiklik İzinleri):\n"
                "İmzadan sonra belgeye hangi değişikliklere izin verileceğini belirler.\n\n"
                "Seçenekler:\n"
                "• Sadece imza: Sadece yeni imza eklenebilir (form/yorum kapalı)\n"
                "• Form doldurma + imza: Form alanları doldurulabilir\n"
                "• Form + yorum + imza: Yorum ve ek açıklamalar için izin verilir\n\n"
                "E-İmza ruhuna uygun olarak, doküman imzalandıktan sonra değişmemelidir.\n"
                "LTV ve TSA'nın birlikte kullanılması, elektronik imzanın hukuki geçerliliğini arttırır."
            )

            help_win = Toplevel(self.root)
            help_win.title(title)
            help_win.geometry("620x500")
            help_win.transient(self.root)
            help_win.grab_set()
            
            frame = ttk.Frame(help_win, padding=12)
            frame.pack(fill=BOTH, expand=YES)
            lbl = ttk.Label(frame, text=body, justify=LEFT, wraplength=580)
            lbl.pack(fill=BOTH, expand=YES)
            ttk.Button(frame, text="Kapat", command=help_win.destroy).pack(anchor=E, pady=(8, 0))
            
            # Center the window on the main window with delayed positioning
            def center_window():
                try:
                    # Get main window center
                    mw = self.root.winfo_width()
                    mh = self.root.winfo_height()
                    mx = self.root.winfo_x()
                    my = self.root.winfo_y()
                    
                    # Get help window size
                    hw = help_win.winfo_width()
                    hh = help_win.winfo_height()
                    
                    # Calculate center position
                    x = mx + (mw - hw) // 2
                    y = my + (mh - hh) // 2
                    
                    help_win.geometry(f"+{max(0, x)}+{max(0, y)}")
                except Exception:
                    pass
            
            # Schedule centering after window is rendered
            help_win.after(100, center_window)
        except Exception as e:
            try:
                messagebox.showinfo("Bilgi", str(e))
            except Exception:
                pass

    def _center_window(self):
        """Center the main window on the screen."""
        try:
            self.root.update_idletasks()
            w = self.root.winfo_width()
            h = self.root.winfo_height()
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            x = max(0, (sw - w) // 2)
            y = max(0, (sh - h) // 2)
            # Preserve current size while setting position
            try:
                self.root.geometry(f"{w}x{h}+{x}+{y}")
            except Exception:
                try:
                    self.root.geometry(f"+{x}+{y}")
                except Exception:
                    pass
        except Exception:
            pass

    def _refresh_sig_info_font(self):
        """Update the font used by the preview signature text label according to UI settings.
        Keeps font size fixed to avoid layout changes; only family and weight change.
        """
        try:
            fam_map = {
                'Segoe': 'Segoe UI',
                'Arial': 'Arial',
                'Times': 'Times New Roman',
                'Verdana': 'Verdana',
                'Tahoma': 'Tahoma',
                'Courier': 'Courier New'
            }
            fam = self.sig_font_var.get() if getattr(self, 'sig_font_var', None) else 'Segoe'
            fam_display = fam_map.get(str(fam).split()[0], 'Segoe UI')
            style = self.sig_style_var.get() if getattr(self, 'sig_style_var', None) else 'Normal'
            weight = 'bold' if str(style).lower().startswith('bold') else 'normal'
            # Keep size constant (8pt in preview)
            try:
                self.sig_info_text_label.configure(font=(fam_display, 8, weight))
            except Exception:
                # fallback to setting options individually
                try:
                    import tkinter as tk
                    f = tk.font.Font(family=fam_display, size=8, weight=weight)
                    self.sig_info_text_label.configure(font=f)
                except Exception:
                    pass
        except Exception:
            pass

    def _add_sign_button_to_pin(self):
        """Add the small sign button next to the PIN entry in auth_frame."""
        try:
            try:
                # If buttons already exist, do nothing
                if getattr(self, 'auth_sign_btn', None) and getattr(self, 'batch_sign_btn', None):
                    return
            except Exception:
                pass
            
            # Create small Imzala button next to pin entry
            self.sign_icon = BootstrapIcon("pen", "✍️", ({"color": "success"}, {"color": "white"}), size=18)
            self.auth_sign_btn = ttk.Button(
                self.auth_frame if hasattr(self, 'auth_frame') else None,
                text=' İmzala',
                image=self.sign_icon.image,
                compound=LEFT,
                bootstyle='success-outline',
                padding=2,
                command=self.do_sign
            )
            self.sign_icon.attach(self.auth_sign_btn)
            
            # Create Toplu İmza button
            self.batch_sign_icon = BootstrapIcon("files", "📄", ({"color": "primary"}, {"color": "white"}), size=18)
            self.batch_sign_btn = ttk.Button(
                self.auth_frame if hasattr(self, 'auth_frame') else None,
                text=' Toplu İmza',
                image=self.batch_sign_icon.image,
                compound=LEFT,
                bootstyle='primary-outline',
                padding=2,
                command=self.do_batch_sign
            )
            self.batch_sign_icon.attach(self.batch_sign_btn)
            
            # Place buttons in the auth_frame row
            try:
                self.auth_sign_btn.grid(row=0, column=2, padx=5, sticky='nsw')
                self.batch_sign_btn.grid(row=0, column=3, padx=5, sticky='nsw')
            except Exception:
                # Fallback: pack into auth_frame if grid fails
                try:
                    self.auth_sign_btn.pack(side=LEFT, padx=0)
                    self.batch_sign_btn.pack(side=LEFT, padx=5)
                except Exception:
                    pass
        except Exception:
            pass

    def _refresh_preview_if_open(self):
        """Refresh the preview if the preview window exists (don't open it)."""
        try:
            if getattr(self, '_preview_win', None) and self._preview_win.winfo_exists():
                # silent redraw
                self._show_signature_preview(silent=True)
        except Exception:
            pass

    def _update_signature_image_display(self):
        """Load and display the current signature image and info text in the template panel."""
        try:
            from PIL import Image, ImageTk
            from sign_pdf import resource_path
            
            # Check config for custom path, fallback to default logo_imza.png
            sig_conf = self.config.get('signature', {})
            img_path_str = sig_conf.get('image_path')
            
            img_path = Path(img_path_str) if img_path_str else resource_path('logo_imza.png')
            
            if img_path.exists():
                img = Image.open(img_path)
                # Sağ sütun genişlediği için maksimum genişliği 330px'e çıkarıyoruz
                img.thumbnail((330, 100), Image.LANCZOS)
                self._sig_photo = ImageTk.PhotoImage(img)
                self.sig_img_label.configure(image=self._sig_photo, text="")
            else:
                self.sig_img_label.configure(image='', text="Görsel bulunamadı\n(logo_imza.png)")
        except Exception as e:
            self.sig_img_label.configure(text=f"Görsel hatası: {e}")
            
        # İmza bilgi metnini güncelle (PDF'deki gerçek görünümü taklit eder)
        try:
            from datetime import datetime
            now = datetime.now().strftime('%d.%m.%Y')
            
            cert_serial = None
            signer_name = "Örnek İmzacı"
            
            cert_display = self._cert_combo_var.get()
            if cert_display and cert_display != '(none)':
                info = self._cert_map.get(cert_display, {})
                signer_name = cert_display.split('|')[0].strip()
                cert_serial = info.get('serial')
            
            token_display = self._token_combo_var.get()
            token_info = self._slot_map.get(token_display) if token_display and token_display != '(none)' else None

            lines = ["İmzalayan:", signer_name, f"Tarih: {now}"]
            
            if cert_serial:
                lines.append(f"SN: {cert_serial}")
            elif cert_display == '(none)':
                # Mock serial for preview when no cert selected
                lines.append(f"SN: 1234567890")

            info_text = "\n".join(lines)
            self.sig_info_text_label.configure(text=info_text)
            try:
                self._refresh_sig_info_font()
            except Exception:
                pass
        except Exception:
            pass

    def _browse_signature_image(self):
        """Open dialog to select a new signature image and update display."""
        path = filedialog.askopenfilename(
            title="İmza Görseli Seçin",
            filetypes=[("Resim Dosyaları", "*.png *.jpg *.jpeg *.bmp *.gif")]
        )
        if path:
            if 'signature' not in self.config:
                self.config['signature'] = {}
            self.config['signature']['image_path'] = path
            save_config(self.config)
            self.log_message(f"🖼️ Yeni imza görseli seçildi: {Path(path).name}")
            self._update_signature_image_display()
            # Also refresh preview if open
            self._refresh_preview_if_open()

    def _on_canvas_enter(self, event):
        """OPSIYON 2 + 3 + Tooltip: Change cursor and add border highlight on canvas hover."""
        try:
            # Opsiyon 2: Change cursor to hand
            self.embedded_canvas.config(cursor="hand2")
            # Opsiyon 3: Highlight wrapper frame background (no layout shift)
            self.canvas_wrapper.config(style="success.TFrame")  # Green background from theme
            # Show tooltip
            self._show_canvas_tooltip(event)
        except Exception:
            pass

    def _on_canvas_leave(self, event):
        """Remove highlight and restore cursor when leaving canvas."""
        try:
            # Restore default cursor
            self.embedded_canvas.config(cursor="arrow")
            # Restore wrapper frame default style
            self.canvas_wrapper.config(style="")  # Reset to default
            # Hide tooltip
            self._hide_canvas_tooltip()
        except Exception:
            pass

    def _on_canvas_motion(self, event):
        """Update tooltip position as mouse moves (only if tooltip is visible)."""
        try:
            if self.canvas_tooltip is not None:
                # Position tooltip near cursor (offset to right and down)
                x = event.x_root + 15
                y = event.y_root + 10
                self.canvas_tooltip.geometry(f"+{x}+{y}")
        except Exception:
            pass

    def _show_canvas_tooltip(self, event):
        """Show tooltip with drag hint near cursor."""
        try:
            if self.canvas_tooltip is None:
                self.canvas_tooltip = Toplevel(self.root)
                self.canvas_tooltip.wm_overrideredirect(True)
                self.canvas_tooltip.wm_attributes('-topmost', True)
                
                label = Label(
                    self.canvas_tooltip,
                    text="Sürükle",
                    font=(FONT_FAMILY, 9),
                    bg="#fff9e6",
                    fg="#333",
                    padx=8,
                    pady=4,
                    relief='solid',
                    borderwidth=1
                )
                label.pack()
                
                # Position near cursor
                x = event.x_root + 15
                y = event.y_root + 10
                self.canvas_tooltip.geometry(f"+{x}+{y}")
        except Exception:
            pass

    def _hide_canvas_tooltip(self):
        """Hide and destroy tooltip."""
        try:
            if self.canvas_tooltip is not None:
                self.canvas_tooltip.destroy()
                self.canvas_tooltip = None
        except Exception:
            pass

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = ModernTTKApp()
    app.run()