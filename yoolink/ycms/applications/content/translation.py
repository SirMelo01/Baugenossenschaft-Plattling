from modeltranslation.translator import TranslationOptions, register

from .models import Customer, ImpressumBlock, PrivacyPolicy, TextContent


@register(TextContent)
class TextContentTranslationOptions(TranslationOptions):
    fields = ("header", "title", "description", "buttonText")


@register(ImpressumBlock)
class ImpressumBlockTranslationOptions(TranslationOptions):
    fields = ("title", "content")


@register(PrivacyPolicy)
class PrivacyPolicyTranslationOptions(TranslationOptions):
    fields = ("content_text", "content_html")


@register(Customer)
class CustomerTranslationOptions(TranslationOptions):
    fields = (
        "subtitle",
        "short_description",
        "description",
        "services_text",
        "testimonial",
        "testimonial_author",
    )
