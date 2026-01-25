from crawl4ai import CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from crawl4ai.content_filter_strategy import PruningContentFilter
from .models import CrawlSettings

WORDPRESS_ELEMENTOR = dict(
    target_elements=[
        "main","article","#content",".entry-content",
        ".elementor-location-single",".elementor-widget-theme-post-content",
        ".e-n-tabs-content",".elementor-tab-content",".elementor-widget-text-editor",
    ],
    excluded_tags=["header","footer","nav","form","aside"],
    excluded_selector=(
        "#masthead, #colophon, .site-header, .site-footer, .widget, .sidebar, "
        ".breadcrumbs, .menu, .elementor-location-header, .elementor-location-footer, "
        ".elementor-nav-menu, .elementor-menu, .elementor-icon-list, "
        ".elementor-widget-social-icons, .elementor-share-buttons"
    ),
)

MED_UNNE_PROFILE = dict(
    target_elements=[
        "main", "article", "#content", ".entry-content",
        ".post-content", ".page-content",
        # Elementor específicos
        ".elementor-location-single",
        ".elementor-widget-theme-post-content",
        ".e-n-tabs-content", ".elementor-tab-content",
        ".elementor-widget-text-editor",
    ],
    excluded_tags=[
        "header", "footer", "nav", "aside", "form",
        "script", "style", "noscript", "menu", "breadcrumb"
    ],
    excluded_selector=(
        # Headers y footers
        "#masthead, #colophon, .site-header, .site-footer, "
        # Widgets y sidebars
        ".widget, .sidebar, .breadcrumbs, "
        # Menús
        ".menu, .nav-menu, .navigation, "
        # Elementor navigation
        ".elementor-location-header, .elementor-location-footer, "
        ".elementor-nav-menu, .elementor-menu, "
        # Social y compartir
        ".elementor-icon-list, .elementor-widget-social-icons, "
        ".elementor-share-buttons, .social-links, .share-buttons, "
        # Comentarios y metadata
        ".comments, .comment-form, .post-meta, .entry-meta, "
        # Publicidad y popups
        ".ad, .advertisement, .popup, .modal"
    ),
)

PROFILES = {
    "wordpress_elementor": WORDPRESS_ELEMENTOR,
    "med_unne": MED_UNNE_PROFILE,
}

def build_run_config(cfg: CrawlSettings) -> CrawlerRunConfig:
    profile = PROFILES[cfg.site_profile]
    # Filtro más agresivo para eliminar boilerplate y bloques cortos (menús, etc.)
    prune = PruningContentFilter(threshold=0.48, threshold_type="dynamic", min_word_threshold=15)
    mdgen = DefaultMarkdownGenerator(content_filter=prune)
    return CrawlerRunConfig(
        target_elements=profile["target_elements"],
        excluded_tags=profile["excluded_tags"],
        excluded_selector=profile["excluded_selector"],
        exclude_social_media_links=False,
        exclude_external_images=True,
        word_count_threshold=0,
        markdown_generator=mdgen,
        cache_mode=CacheMode.BYPASS if cfg.bypass_cache else CacheMode.ENABLED,
    )
