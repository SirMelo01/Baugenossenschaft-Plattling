from django.core.files.storage import FileSystemStorage
from storages.backends.s3boto3 import S3Boto3Storage


class MediaRootS3Boto3Storage(S3Boto3Storage):
    location = 'media'


class PrivateMediaS3Boto3Storage(S3Boto3Storage):
    """Ablage fuer Dateien, die niemals oeffentlich abrufbar sein duerfen.

    Der Standard-Storage des Projekts legt alles mit ``ACL: public-read`` und
    ohne Signatur ab - jede hochgeladene Datei haette damit eine dauerhaft
    oeffentliche Adresse. Fuer Anhaenge aus den Kontaktformularen (ausgefuellte
    Selbstauskunft, Fotos aus der Wohnung) waere das ein Datenschutzvorfall.

    Diese Ablage setzt deshalb ausdruecklich ``private`` und haengt eine Signatur
    an die Adresse. Ausgeliefert werden die Dateien trotzdem nur ueber die
    geschuetzte Ansicht im CMS, die eine Anmeldung verlangt.
    """

    location = 'private/bgp/kontakt-anhaenge'
    default_acl = 'private'
    querystring_auth = True
    file_overwrite = False
    object_parameters = {"CacheControl": "no-store"}


class PrivateFileSystemStorage(FileSystemStorage):
    """Private Ablage im Dateisystem (Entwicklung und Tests).

    ``FileSystemStorage`` faellt bei ``base_url=None`` auf ``MEDIA_URL`` zurueck
    und liefert dann eine Adresse wie ``/media/anfragen/12/abc.jpg``. Die sieht
    oeffentlich aus, zeigt aber ins Leere - und wuerde tatsaechlich oeffentlich,
    sobald jemand PRIVATE_MEDIA_ROOT unter MEDIA_ROOT legt.

    Deshalb gibt es hier gar keine Adresse: ``url()`` scheitert laut. Ein
    Template, das versehentlich direkt verlinkt, faellt sofort auf, statt still
    personenbezogene Dateien preiszugeben. Ausgeliefert wird ausschliesslich
    ueber die angemeldete CMS-Ansicht.
    """

    def url(self, name):
        raise ValueError(
            "Anhänge haben bewusst keine öffentliche Adresse. "
            "Bitte die geschützte CMS-Ansicht verwenden (cms:message-attachment)."
        )
