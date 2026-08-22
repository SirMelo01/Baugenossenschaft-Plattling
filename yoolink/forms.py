from django import forms
from django_recaptcha.fields import ReCaptchaField
from django_recaptcha.widgets import ReCaptchaV3

from yoolink.ycms.contact_attachments import prepare_attachments
from yoolink.ycms.models import Message, MessageAttachment


class ContactForm(forms.Form):
    """Formular der YooLink-Seite und der ``/api/email/``-Schnittstelle."""

    name = forms.CharField(max_length=100)
    email = forms.EmailField()
    title = forms.CharField(max_length=100)
    message = forms.CharField(widget=forms.Textarea)
    captcha = ReCaptchaField(widget=ReCaptchaV3)


# ---------------------------------------------------------------------------
# Kontaktformulare der Baugenossenschaft Plattling
# ---------------------------------------------------------------------------
# Die Kontaktseite bietet drei Formulare an: allgemeine Anfrage, Bewerbung um
# eine Mitgliedschaft und Reparaturmeldung. Gemeinsam sind allen Name, E-Mail,
# Telefon, Nachricht und die Datenschutz-Zustimmung; alles Weitere ist je
# Formular verschieden und landet ueber ``detail_rows()`` in ``Message.details``,
# damit nicht jedes Formular eigene Datenbankspalten braucht.

ANREDE_CHOICES = [
    ("", "Bitte wählen"),
    ("Frau", "Frau"),
    ("Herr", "Herr"),
    ("Divers", "Divers"),
    ("Keine Angabe", "Keine Angabe"),
]

_FIELD_CLASS = "bgp-field"
_CHECKBOX_CLASS = "bgp-checkbox bgp-focus"


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """Dateifeld, das mehrere Dateien annimmt.

    Django bringt dafuer nichts Fertiges mit; das hier ist das in der
    Django-Dokumentation beschriebene Vorgehen. ``clean`` liefert immer eine
    Liste - auch bei einer einzelnen oder gar keiner Datei.
    """

    widget = MultipleFileInput

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single = super().clean
        if isinstance(data, (list, tuple)):
            return [single(item, initial) for item in data if item]
        if data in self.empty_values:
            return []
        return [single(data, initial)]


class BgpContactBaseForm(forms.Form):
    """Gemeinsame Felder, Validierung und Spam-Falle der drei Kontaktformulare."""

    # Fehlerhafte Felder bekommen ueber ``BoundField.css_classes`` eine Klasse am
    # umgebenden Block; die Umrandung faerbt dann das Stylesheet der Kontaktseite.
    error_css_class = "has-error"

    # Wert des ``formular``-Feldes und zugleich ``Message.category``.
    category = Message.Category.GENERAL
    # Beschriftung, die im Betreff der Anfrage steht, wenn das Formular keinen
    # eigenen Betreff abfragt.
    subject_prefix = "Kontaktanfrage"
    # Beschriftung des Anhang-Feldes und der einzelnen Datei in Fehlermeldungen.
    attachment_label = "Dateien anhängen"
    attachment_item_label = "Datei"

    anrede = forms.ChoiceField(
        label="Anrede",
        choices=ANREDE_CHOICES,
        required=False,
    )
    name = forms.CharField(
        label="Name",
        max_length=70,
        error_messages={"required": "Bitte geben Sie Ihren Namen an."},
    )
    email = forms.EmailField(
        label="E-Mail",
        max_length=60,
        error_messages={
            "required": "Bitte geben Sie eine E-Mail-Adresse an.",
            "invalid": "Bitte geben Sie eine gültige E-Mail-Adresse an.",
        },
    )
    telefon = forms.CharField(label="Telefon", max_length=40, required=False)
    nachricht = forms.CharField(
        label="Nachricht",
        max_length=3000,
        widget=forms.Textarea(attrs={"rows": 6}),
        error_messages={"required": "Bitte schreiben Sie uns ein paar Zeilen."},
    )
    datenschutz = forms.BooleanField(
        label="Datenschutz",
        error_messages={"required": "Bitte bestätigen Sie die Datenschutzerklärung."},
    )
    # Anhaenge sind immer freiwillig. Ob das Feld ueberhaupt erscheint, entscheidet
    # die im CMS gepflegte Einstellung je Formular (siehe ``__init__``).
    anhaenge = MultipleFileField(
        label="Dateien anhängen",
        required=False,
    )
    # Honigtopf: ein ganz normales Textfeld, das im Template per CSS aus dem Blick
    # genommen und aus der Tabreihenfolge entfernt wird. Menschen sehen es nie,
    # Formular-Bots fuellen es aus - und scheitern dann an der Validierung.
    website = forms.CharField(
        required=False,
        label="Bitte nicht ausfüllen",
        widget=forms.TextInput(attrs={"autocomplete": "off", "tabindex": "-1"}),
    )

    def __init__(self, *args, attachment_settings=None, **kwargs):
        # Alle drei Formulare stehen gleichzeitig auf der Kontaktseite. Ohne
        # eigenes Praefix vergaeben sie dieselben ``id``-Werte - ein Klick auf
        # "Name" im Reparaturformular landete dann im allgemeinen Formular.
        kwargs.setdefault("auto_id", f"id_{self.category}_%s")
        super().__init__(*args, **kwargs)

        # Die Einstellung sagt, ob dieses Formular Dateien annimmt und welche.
        # Ist das abgeschaltet, verschwindet das Feld ganz - dann kann auch ueber
        # eine nachgebaute Anfrage nichts hochgeladen werden.
        self.attachment_settings = attachment_settings
        if attachment_settings is None or not attachment_settings.uploads_enabled:
            self.fields.pop("anhaenge", None)
        else:
            anhaenge = self.fields["anhaenge"]
            anhaenge.label = self.attachment_label
            anhaenge.widget.attrs["accept"] = attachment_settings.accept_attribute
            anhaenge.widget.attrs["multiple"] = "multiple"

        for name, field in self.fields.items():
            if name == "website":
                continue
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", _CHECKBOX_CLASS)
            else:
                widget.attrs.setdefault("class", _FIELD_CLASS)
            # ``required`` im Markup laesst den Browser die Pflichtfelder pruefen;
            # die Meldung dazu kommt aus dem Skript der Kontaktseite.
            if field.required:
                widget.attrs.setdefault("required", "required")

    def clean_website(self):
        if (self.cleaned_data.get("website") or "").strip():
            raise forms.ValidationError("Ungültige Eingabe.")
        return ""

    def clean_anhaenge(self):
        """Hochgeladene Dateien pruefen und bereinigen.

        Die eigentliche Arbeit macht ``contact_attachments``: Art anhand des
        Inhalts bestimmen, Bilder neu schreiben, Groessen begrenzen. Was hier
        herauskommt, ist bereits unbedenklich und muss nur noch abgelegt werden.
        """
        uploads = self.cleaned_data.get("anhaenge") or []
        settings_obj = self.attachment_settings
        if not uploads or settings_obj is None:
            return []

        allowed = settings_obj.allowed_kinds
        if not allowed:
            raise forms.ValidationError("Für dieses Formular sind derzeit keine Anhänge vorgesehen.")

        return prepare_attachments(
            uploads,
            allowed_kinds=allowed,
            max_files=settings_obj.max_uploads,
            label=self.attachment_item_label,
        )

    def clean_nachricht(self):
        text = (self.cleaned_data.get("nachricht") or "").strip()
        if len(text) < 10:
            raise forms.ValidationError("Bitte beschreiben Sie Ihr Anliegen in ein paar Sätzen.")
        return text

    # -- Ergebnis ----------------------------------------------------------

    def subject(self) -> str:
        """Betreff der Anfrage (Spalte ``Message.title``)."""
        return self.subject_prefix

    def detail_rows(self) -> list:
        """Zusatzangaben des Formulars als geordnete ``label``/``value``-Liste."""
        return []

    def _rows(self, *pairs) -> list:
        """Hilfsfunktion: leere Angaben aus der Liste werfen."""
        rows = []
        for label, value in pairs:
            if value in (None, "", []):
                continue
            if not isinstance(value, str):
                value = str(value)
            value = value.strip()
            if value:
                rows.append({"label": label, "value": value})
        return rows

    def save(self) -> Message:
        data = self.cleaned_data
        anrede = data.get("anrede") or ""
        name = data["name"].strip()
        if anrede and anrede != "Keine Angabe":
            name = f"{anrede} {name}"
        message = Message.objects.create(
            category=self.category,
            name=name[:70],
            email=data["email"].strip(),
            phone=(data.get("telefon") or "").strip(),
            title=self.subject()[:100],
            message=data["nachricht"],
            details=self.detail_rows(),
        )

        for item in data.get("anhaenge") or []:
            attachment = MessageAttachment(
                message=message,
                original_name=item.original_name,
                content_type=item.content_type,
                kind=item.kind,
                size=item.size,
            )
            # ``storage_name`` ist der Zufallsname aus der Pruefung - der Name des
            # Besuchers kommt nie in die Ablage.
            attachment.file.save(item.storage_name, item.content, save=False)
            attachment.save()

        return message


class BgpGeneralContactForm(BgpContactBaseForm):
    """Allgemeine Anfrage an die Genossenschaft."""

    category = Message.Category.GENERAL
    subject_prefix = "Kontaktanfrage"

    BETREFF_CHOICES = [
        ("", "Bitte wählen"),
        ("Wohnungsanfrage / Interessentenliste", "Wohnungsanfrage / Interessentenliste"),
        ("Mitgliedschaft & Geschäftsanteile", "Mitgliedschaft & Geschäftsanteile"),
        ("Anliegen als Mieter", "Anliegen als Mieter"),
        ("Frage zur Betriebskostenabrechnung", "Frage zur Betriebskostenabrechnung"),
        ("Sonstiges", "Sonstiges"),
    ]

    betreff = forms.ChoiceField(
        label="Ihr Anliegen",
        choices=BETREFF_CHOICES,
        error_messages={"required": "Bitte wählen Sie ein Anliegen aus."},
    )

    field_order = ["anrede", "name", "email", "telefon", "betreff", "nachricht", "anhaenge", "datenschutz"]

    def subject(self) -> str:
        return self.cleaned_data.get("betreff") or self.subject_prefix


class BgpMembershipForm(BgpContactBaseForm):
    """Bewerbung um eine Mitgliedschaft in der Genossenschaft."""

    category = Message.Category.MEMBERSHIP
    subject_prefix = "Bewerbung um eine Mitgliedschaft"
    attachment_label = "Ausgefüllte Selbstauskunft anhängen"
    attachment_item_label = "Selbstauskunft"

    HAUSHALT_CHOICES = [
        ("", "Bitte wählen"),
        ("1 Person", "1 Person"),
        ("2 Personen", "2 Personen"),
        ("3 Personen", "3 Personen"),
        ("4 Personen", "4 Personen"),
        ("5 Personen oder mehr", "5 Personen oder mehr"),
    ]
    WOHNUNG_CHOICES = [
        ("", "Keine Angabe"),
        ("1 Zimmer", "1 Zimmer"),
        ("2 Zimmer", "2 Zimmer"),
        ("3 Zimmer", "3 Zimmer"),
        ("4 Zimmer oder mehr", "4 Zimmer oder mehr"),
    ]

    geburtsdatum = forms.DateField(
        label="Geburtsdatum",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        error_messages={"invalid": "Bitte geben Sie ein gültiges Geburtsdatum an."},
    )
    strasse = forms.CharField(label="Straße und Hausnummer", max_length=120, required=False)
    plz_ort = forms.CharField(label="PLZ und Ort", max_length=120, required=False)
    haushalt = forms.ChoiceField(
        label="Personen im Haushalt",
        choices=HAUSHALT_CHOICES,
        error_messages={"required": "Bitte geben Sie die Haushaltsgröße an."},
    )
    wohnungsgroesse = forms.ChoiceField(
        label="Gewünschte Wohnungsgröße",
        choices=WOHNUNG_CHOICES,
        required=False,
    )
    einzug = forms.DateField(
        label="Gewünschter Einzugstermin",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        error_messages={"invalid": "Bitte geben Sie ein gültiges Datum an."},
    )
    ist_mitglied = forms.BooleanField(
        label="Ich bin bereits Mitglied der Genossenschaft",
        required=False,
    )

    field_order = [
        "anrede", "name", "geburtsdatum", "email", "telefon",
        "strasse", "plz_ort", "haushalt", "wohnungsgroesse", "einzug",
        "ist_mitglied", "nachricht", "anhaenge", "datenschutz",
    ]

    def detail_rows(self) -> list:
        data = self.cleaned_data
        geburtsdatum = data.get("geburtsdatum")
        einzug = data.get("einzug")
        anschrift = " ".join(part for part in [data.get("strasse"), data.get("plz_ort")] if part)
        return self._rows(
            ("Geburtsdatum", geburtsdatum.strftime("%d.%m.%Y") if geburtsdatum else ""),
            ("Anschrift", anschrift),
            ("Personen im Haushalt", data.get("haushalt")),
            ("Gewünschte Wohnungsgröße", data.get("wohnungsgroesse")),
            ("Gewünschter Einzug", einzug.strftime("%d.%m.%Y") if einzug else ""),
            ("Bereits Mitglied", "Ja" if data.get("ist_mitglied") else "Nein"),
        )


class BgpRepairForm(BgpContactBaseForm):
    """Reparaturanfrage eines Mitglieds zu seiner Wohnung."""

    category = Message.Category.REPAIR
    subject_prefix = "Reparaturanfrage"
    attachment_label = "Fotos vom Schaden anhängen"
    attachment_item_label = "Foto"

    SCHADEN_CHOICES = [
        ("", "Bitte wählen"),
        ("Heizung / Warmwasser", "Heizung / Warmwasser"),
        ("Sanitär / Abfluss", "Sanitär / Abfluss"),
        ("Elektro", "Elektro"),
        ("Fenster / Türen", "Fenster / Türen"),
        ("Schließanlage / Briefkasten", "Schließanlage / Briefkasten"),
        ("Feuchtigkeit / Schimmel", "Feuchtigkeit / Schimmel"),
        ("Außenanlage / Gemeinschaftsflächen", "Außenanlage / Gemeinschaftsflächen"),
        ("Sonstiges", "Sonstiges"),
    ]
    DRINGLICHKEIT_CHOICES = [
        ("Normal", "Normal - im Rahmen der üblichen Bearbeitung"),
        ("Dringend", "Dringend - Wohnung ist beeinträchtigt"),
    ]

    mitgliedsnummer = forms.CharField(label="Mitgliedsnummer", max_length=40, required=False)
    objekt = forms.CharField(
        label="Objekt / Anschrift der Wohnung",
        max_length=160,
        error_messages={"required": "Bitte geben Sie an, um welche Wohnung es geht."},
    )
    wohnungslage = forms.CharField(label="Lage der Wohnung", max_length=80, required=False)
    schadensart = forms.ChoiceField(
        label="Art des Schadens",
        choices=SCHADEN_CHOICES,
        error_messages={"required": "Bitte wählen Sie die Art des Schadens aus."},
    )
    dringlichkeit = forms.ChoiceField(
        label="Dringlichkeit",
        choices=DRINGLICHKEIT_CHOICES,
        initial="Normal",
        required=False,
    )
    erreichbarkeit = forms.CharField(
        label="Wann sind Sie erreichbar?",
        max_length=160,
        required=False,
    )

    field_order = [
        "anrede", "name", "mitgliedsnummer", "email", "telefon",
        "objekt", "wohnungslage", "schadensart", "dringlichkeit",
        "erreichbarkeit", "nachricht", "anhaenge", "datenschutz",
    ]

    def subject(self) -> str:
        schaden = self.cleaned_data.get("schadensart") or "Reparatur"
        return f"Reparatur: {schaden}"

    def detail_rows(self) -> list:
        data = self.cleaned_data
        return self._rows(
            ("Mitgliedsnummer", data.get("mitgliedsnummer")),
            ("Objekt / Anschrift", data.get("objekt")),
            ("Lage der Wohnung", data.get("wohnungslage")),
            ("Art des Schadens", data.get("schadensart")),
            ("Dringlichkeit", data.get("dringlichkeit") or "Normal"),
            ("Erreichbarkeit", data.get("erreichbarkeit")),
        )


# ``formular``-Wert der Kontaktseite -> Formularklasse. Dieselben Schluessel
# stehen in ``BGP_CONTACT_TABS`` (Aufbau der Reiter) und in den CMS-Bausteinen
# ``contact_form_<key>`` (Texte) - beides in
# ``yoolink/ycms/applications/content/bgp_content.py``.
BGP_CONTACT_FORMS = {
    "allgemein": BgpGeneralContactForm,
    "mitgliedschaft": BgpMembershipForm,
    "reparatur": BgpRepairForm,
}
BGP_DEFAULT_CONTACT_FORM = "allgemein"
