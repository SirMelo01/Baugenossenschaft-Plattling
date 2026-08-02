from modeltranslation.translator import register, TranslationOptions
from .models import FAQ, AnyFile, UserSettings, VideoFile, WebsiteSettings, fileentry, GaleryImage, Galerie, Button, PricingCard, PricingFeature

@register(FAQ)
class FAQTranslationOptions(TranslationOptions):
    fields = ('question', 'answer')

@register(fileentry)
class FileEntryTranslationOptions(TranslationOptions):
    fields = ('title',)

@register(GaleryImage)
class GaleryImageTranslationOptions(TranslationOptions):
    fields = ('title',)

@register(Galerie)
class GalerieTranslationOptions(TranslationOptions):
    fields = ('title', 'description')

@register(Button)
class ButtonTranslationOptions(TranslationOptions):
    fields = ('text', 'hover_text')

@register(PricingCard)
class PricingCardTranslationOptions(TranslationOptions):
    fields = ('title', 'description')

@register(PricingFeature)
class PricingFeatureTranslationOptions(TranslationOptions):
    fields = ('text',)

# Files
# Beliebige Dateien (pdf, zip, docx, …)
@register(AnyFile)
class AnyFileTranslationOptions(TranslationOptions):
    fields = ('title', 'description',)

# Video-Dateien (mit SEO-Feldern)
@register(VideoFile)
class VideoFileTranslationOptions(TranslationOptions):
    # WICHTIG: slug NICHT übersetzen (unique Konflikte). Nur Inhalte/SEO-Felder.
    fields = ('title', 'description', 'alt_text', 'tags', 'place',)

@register(UserSettings)
class UserSettingsTranslationOptions(TranslationOptions):
    fields = (
        'vacationText',
    )


@register(WebsiteSettings)
class WebsiteSettingsTranslationOptions(TranslationOptions):
    fields = (
        'vacationText',
    )
