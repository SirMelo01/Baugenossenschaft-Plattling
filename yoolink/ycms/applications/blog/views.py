from django.db import transaction
from django.urls import reverse
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import extend_schema

from yoolink.ycms.models import Blog, DeveloperApiConnectAuthorization, DeveloperApiKey

from .authentication import DeveloperApiKeyAuthentication
from .permissions import HasDeveloperApiKeyScope
from .serializers import (
    ExternalBlogImageUploadSerializer,
    ExternalApiPingSerializer,
    ExternalBlogListSerializer,
    ExternalBlogSerializer,
    ExternalConnectTokenRequestSerializer,
    ExternalConnectTokenResponseSerializer,
)


class ExternalBlogViewSet(ModelViewSet):
    serializer_class = ExternalBlogSerializer
    authentication_classes = [DeveloperApiKeyAuthentication]
    permission_classes = [HasDeveloperApiKeyScope]
    parser_classes = [JSONParser, FormParser, MultiPartParser]
    api_app_code = DeveloperApiKey.APP_BLOG

    def get_serializer_class(self):
        if self.action == "upload_media":
            return ExternalBlogImageUploadSerializer

        if self.action == "list":
            return ExternalBlogListSerializer

        return ExternalBlogSerializer

    @action(detail=False, methods=["post"], url_path="media")
    def upload_media(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.save(), status=status.HTTP_201_CREATED)

    def get_queryset(self):
        queryset = (
            Blog.objects
            .select_related("author", "original")
            .prefetch_related("translations")
            .order_by("-date", "-id")
        )

        query = (self.request.query_params.get("q") or "").strip()
        if query:
            queryset = queryset.filter(title__icontains=query)

        language = (self.request.query_params.get("language") or "").strip()
        if language:
            queryset = queryset.filter(language=language)

        active = (self.request.query_params.get("active") or "").lower()
        if active in ("true", "1", "yes"):
            queryset = queryset.filter(active=True)
        elif active in ("false", "0", "no"):
            queryset = queryset.filter(active=False)

        original_only = (self.request.query_params.get("original_only") or "").lower()
        if original_only in ("true", "1", "yes"):
            queryset = queryset.filter(original__isnull=True)

        return queryset


class ExternalApiPingView(APIView):
    authentication_classes = [DeveloperApiKeyAuthentication]
    permission_classes = [HasDeveloperApiKeyScope]

    @extend_schema(
        operation_id="developer_api_ping",
        summary="Developer API Ping",
        description="Prüft, ob der API-Key gültig ist und die YooLink Developer API erreichbar ist.",
        responses=ExternalApiPingSerializer,
    )
    def get(self, request):
        api_key = request.auth
        return Response(
            {
                "ok": True,
                "message": "YooLink Developer API ist erreichbar und authentifiziert.",
                "authenticated": True,
                "user": request.user.get_username(),
                "access_level": api_key.access_level,
                "allowed_apps": api_key.allowed_apps,
            }
        )


class ExternalConnectTokenView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    parser_classes = [JSONParser, FormParser]

    @extend_schema(
        operation_id="developer_connect_token",
        summary="Developer Connect Token Exchange",
        description=(
            "Tauscht einen kurzlebigen YooLink Connect Authorization Code plus "
            "PKCE Code Verifier gegen einen Developer API Key."
        ),
        request=ExternalConnectTokenRequestSerializer,
        responses={200: ExternalConnectTokenResponseSerializer},
    )
    def post(self, request):
        serializer = ExternalConnectTokenRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        code_hash = DeveloperApiConnectAuthorization.make_code_hash(data["code"])
        with transaction.atomic():
            try:
                authorization = (
                    DeveloperApiConnectAuthorization.objects
                    .select_for_update()
                    .select_related("created_by")
                    .get(code_hash=code_hash)
                )
            except DeveloperApiConnectAuthorization.DoesNotExist:
                return Response(
                    {"error": "invalid_grant", "error_description": "Der Connect Code ist ungültig."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not authorization.is_usable():
                return Response(
                    {"error": "invalid_grant", "error_description": "Der Connect Code ist abgelaufen oder wurde bereits benutzt."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if authorization.redirect_uri != data["redirect_uri"]:
                return Response(
                    {"error": "invalid_grant", "error_description": "redirect_uri passt nicht zum Connect Code."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not authorization.verify_code_verifier(data["code_verifier"]):
                return Response(
                    {"error": "invalid_grant", "error_description": "code_verifier ist ungültig."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not authorization.created_by.is_active:
                return Response(
                    {"error": "invalid_grant", "error_description": "Der YooLink Benutzer ist deaktiviert."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            api_key, raw_api_key = DeveloperApiKey.issue_key(
                created_by=authorization.created_by,
                name=f"{authorization.client_name} Connect",
                access_level=authorization.access_level,
                allowed_apps=authorization.allowed_apps,
            )
            authorization.mark_used()

        return Response(
            {
                "token_type": "Bearer",
                "api_key": raw_api_key,
                "base_url": request.build_absolute_uri("/api/cms/"),
                "ping_url": request.build_absolute_uri("/api/ping/"),
                "docs_url": request.build_absolute_uri(reverse("api-docs")),
                "schema_url": request.build_absolute_uri(reverse("api-schema")),
                "access_level": api_key.access_level,
                "allowed_apps": api_key.allowed_apps,
            }
        )
