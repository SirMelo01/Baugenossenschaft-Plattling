from drf_spectacular.extensions import OpenApiAuthenticationExtension


class DeveloperApiKeyAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "yoolink.ycms.applications.blog.authentication.DeveloperApiKeyAuthentication"
    name = "YooLinkDeveloperApiKey"

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "YooLink Developer API Key",
            "description": (
                "Developer API Key aus dem YooLink CMS. Primär als "
                "`Authorization: Bearer <api-key>` senden. Alternativ wird "
                "`X-YooLink-API-Key: <api-key>` akzeptiert."
            ),
        }
