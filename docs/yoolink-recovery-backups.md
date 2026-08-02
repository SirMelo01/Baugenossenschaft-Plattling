# YooLink Recovery Backups

Diese Anleitung beschreibt die Backup- und Recovery-Funktion im CMS unter `Einstellungen -> Recovery`.

## Ziel

YooLink kann zwei Arten von Backups erstellen:

- Lokaler Download im CMS: Ein berechtigter Nutzer lädt ein ZIP direkt im Browser herunter.
- Remote-Backup: Die App erstellt ein Backup im Hintergrund, verschlüsselt es und lädt es privat in DigitalOcean Spaces hoch.

Remote-Backups sind für den Notfall gedacht, z. B. wenn der Server oder die lokale Datenbank nicht mehr verfügbar ist. Der Source Code liegt separat in Git; das Recovery-Backup enthält die CMS-/Datenbankdaten und optional Medienreferenzen bzw. Medien.

## Sicherheit

Remote-Backups enthalten sensible Daten wie Nutzer, Rollen, Sessions, Passwort-Hashes und CMS-Inhalte. Deshalb gelten diese Regeln:

- Remote-Backups werden vor dem Upload app-seitig verschlüsselt.
- Der Upload zu DigitalOcean Spaces nutzt `ACL=private`.
- Es werden keine öffentlichen Download-URLs im CMS angezeigt.
- Der normale Media-Storage bleibt getrennt vom Backup-Upload.
- Der Encryption-Key darf nie in Git committed werden.
- Ohne Encryption-Key kann ein Remote-Backup nicht entschlüsselt werden.

Die Verschlüsselung nutzt AES-GCM über `cryptography`. Das ist authentifizierte Verschlüsselung: Manipulierte Backup-Dateien werden beim Entschlüsseln erkannt.

## Benötigte Env-Variablen

Diese Variablen können in `.envs/.production/.django` gesetzt werden. In `base.py` und `production.py` existieren Defaults für die meisten Werte; der Encryption-Key muss produktiv explizit gesetzt werden.

```env
RECOVERY_REMOTE_BACKUPS_ENABLED=True
RECOVERY_AUTO_BACKUPS_ENABLED=True
RECOVERY_BACKUP_ENCRYPTION_KEY=<base64-32-byte-key>
RECOVERY_BACKUP_BUCKET_NAME=yoolink
RECOVERY_BACKUP_PREFIX=private/recovery-backups
RECOVERY_REMOTE_BACKUP_ROTATION_SLOTS=2
RECOVERY_REMOTE_BACKUP_INCLUDE_MEDIA=False
```

Zusätzlich nutzt der Remote-Backup-Upload die bestehenden DigitalOcean/S3-Werte:

```env
AWS_ACCESS_KEY_ID=<digitalocean-spaces-access-key>
AWS_SECRET_ACCESS_KEY=<digitalocean-spaces-secret-key>
AWS_S3_ENDPOINT_URL=https://fra1.digitaloceanspaces.com/
```

Optional kann `RECOVERY_BACKUP_BUCKET_NAME` auf einen eigenen privaten Backup-Space zeigen. Empfohlen ist ein eigener Space oder mindestens ein eigener Prefix, z. B. `private/recovery-backups`.

## Encryption-Key erstellen

Den Key auf einem sicheren Rechner oder Server erzeugen:

```bash
docker compose -f production.yml run --rm django python -c "import base64; from cryptography.hazmat.primitives.ciphers.aead import AESGCM; print(base64.urlsafe_b64encode(AESGCM.generate_key(bit_length=256)).decode())"
```

Alternativ lokal:

```bash
python -c "import base64; from cryptography.hazmat.primitives.ciphers.aead import AESGCM; print(base64.urlsafe_b64encode(AESGCM.generate_key(bit_length=256)).decode())"
```

Den ausgegebenen Wert als `RECOVERY_BACKUP_ENCRYPTION_KEY` setzen.

Wichtig:

- Den Key in einem Passwortmanager oder Secret Store sichern.
- Den Key nicht rotieren, ohne alte Backups kontrolliert neu zu verschlüsseln oder alte Keys aufzubewahren.
- Wenn der Key verloren geht, sind die verschlüsselten Remote-Backups nicht mehr nutzbar.

## Automatische Backups

In Production wird bei aktivierten Variablen automatisch ein monatliches Remote-Backup erstellt:

- Zeitpunkt: am 1. Tag des Monats um 03:00 Uhr
- Ausführung: Celery Beat startet `yoolink.ycms.tasks.create_remote_recovery_backup`
- Rotation: zwei Slots, `slot-1.enc` und `slot-2.enc`
- Beim dritten erfolgreichen Backup wird wieder `slot-1.enc` überschrieben.

Die Rotation ist bewusst klein gehalten, damit nicht unbegrenzt sensible Daten gespeichert werden. Falls mehr Historie benötigt wird:

```env
RECOVERY_REMOTE_BACKUP_ROTATION_SLOTS=3
```

Dann entstehen `slot-1.enc`, `slot-2.enc`, `slot-3.enc`.

## Manuelle Remote-Backups

Im CMS:

1. Als Nutzer mit `recovery.manage` anmelden.
2. `Einstellungen -> Recovery` öffnen.
3. Unter `Automatische Backups` auf `Remote-Backup starten` klicken.
4. Der Lauf wird in der Liste `Letzte Remote-Backups` angezeigt.
5. Erfolgreiche Einträge können dort direkt über `Wiederherstellen` ausgewählt werden.

Der Button ist deaktiviert, wenn die Remote-Backup-Konfiguration unvollständig ist.

## Lokaler Backup-Download

Im CMS:

1. `Einstellungen -> Recovery` öffnen.
2. Optional `Medien-Dateien im ZIP mitsichern` aktivieren oder deaktivieren.
3. `Backup herunterladen` klicken.

Lokale Downloads werden direkt im Browser gespeichert. Diese Datei ist nicht automatisch verschlüsselt. Sie muss entsprechend sicher abgelegt werden.

## Medien in Remote-Backups

Standard:

```env
RECOVERY_REMOTE_BACKUP_INCLUDE_MEDIA=False
```

Das ist für Production sinnvoll, wenn Medien bereits in DigitalOcean Spaces/CDN liegen. Das Remote-Backup enthält dann DB und Manifest, aber keine vollständige Kopie aller Medien-Dateien.

Wenn Medien trotzdem mitgesichert werden sollen:

```env
RECOVERY_REMOTE_BACKUP_INCLUDE_MEDIA=True
```

Das kann große Backups erzeugen und lange dauern.

## DigitalOcean Spaces Setup

Der Code erstellt aktuell keinen Space/Bucket automatisch. Das ist absichtlich konservativ:

- Bucket-/Space-Erstellung benötigt weitreichendere Rechte.
- Die laufende App sollte möglichst nur lesen/schreiben dürfen, was sie wirklich braucht.
- Automatische Bucket-Erstellung in der App erhöht das Risiko bei geleakten App-Credentials.

Empfohlen:

1. Einen eigenen Space für Backups in DigitalOcean anlegen, z. B. `yoolink-recovery-backups`.
2. Den Space nicht öffentlich machen.
3. Access Key/Secret mit möglichst engem Zugriff verwenden.
4. `RECOVERY_BACKUP_BUCKET_NAME=yoolink-recovery-backups` setzen.
5. `RECOVERY_BACKUP_PREFIX=private/recovery-backups` setzen.

Falls derselbe Space wie für Medien genutzt wird, sind Backups trotzdem verschlüsselt und werden mit `ACL=private` hochgeladen. Sicherer ist aber ein eigener Backup-Space.

## Restore im Notfall

Voraussetzungen:

- aktueller YooLink Source Code
- neue Datenbank/Installation
- verschlüsselte `.enc` Backup-Datei aus DigitalOcean Spaces oder funktionierende Remote-Backup-Konfiguration im CMS
- exakt derselbe `RECOVERY_BACKUP_ENCRYPTION_KEY`
- Env-Secrets der neuen Installation, z. B. Datenbank, Django Secret Key, DigitalOcean/S3-Zugang
- verfügbare Medien im Media-Storage/CDN oder ein Backup, das Medien mit `RECOVERY_REMOTE_BACKUP_INCLUDE_MEDIA=True` enthält

Ablauf:

1. Projekt auf neuem Server deployen.
2. Env inklusive `RECOVERY_BACKUP_ENCRYPTION_KEY` setzen.
3. Migrationen ausführen.
4. Superuser/Owner-Zugang herstellen.
5. Im CMS `Einstellungen -> Recovery` öffnen.
6. Entweder ein erfolgreiches Remote-Backup in der Liste wählen oder eine `.enc` Datei als Backup-ZIP auswählen.
7. Sicherheitsphrase eingeben.
8. Restore starten.

Der Restore-Pfad erkennt YooLink-verschlüsselte Backups automatisch am Header, entschlüsselt sie mit dem Key und verarbeitet danach den normalen ZIP-Dump.

Wichtig: Die `.enc` Datei enthält den vollständigen Django-Datenbankdump inklusive Nutzer, Rollen, Rechte, Passwort-Hashes und CMS-Inhalte. Sie enthält keine produktiven Env-Secrets und standardmäßig keine Medien-Binaries, wenn `RECOVERY_REMOTE_BACKUP_INCLUDE_MEDIA=False` gesetzt ist. In diesem Standardfall zeigen die wiederhergestellten Daten auf die bestehenden Medien im DigitalOcean/CDN-Storage.

## Deployment-Checkliste

Nach Code-Deployment:

```bash
docker compose -f production.yml build
docker compose -f production.yml run --rm django python manage.py migrate
docker compose -f production.yml run --rm django python manage.py check --deploy --settings=config.settings.production
docker compose -f production.yml up -d
```

Danach im CMS prüfen:

- `Einstellungen -> Recovery` lädt ohne Fehler.
- Remote-Backup-Konfiguration ist grün.
- Ein manuelles Remote-Backup kann gestartet werden.
- In DigitalOcean Spaces erscheint `slot-1.enc`.
- Das Objekt ist nicht öffentlich abrufbar.
- Erfolgreiche Remote-Backups werden in der Liste mit `Wiederherstellen` angeboten.

## Fehlersuche

`relation "ycms_recoverybackup" does not exist`:

```bash
docker compose -f local.yml run --rm django python manage.py migrate
```

Remote-Backup-Button deaktiviert:

- `RECOVERY_REMOTE_BACKUPS_ENABLED`
- `RECOVERY_BACKUP_ENCRYPTION_KEY`
- `RECOVERY_BACKUP_BUCKET_NAME`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_S3_ENDPOINT_URL`

Remote-Backup schlägt fehl:

- Celery Worker läuft?
- Celery Beat läuft?
- Bucket/Space existiert?
- Access Key hat Schreibrechte?
- Encryption-Key ist gültig base64 und enthält 32 Byte?

Key validieren:

```bash
docker compose -f production.yml run --rm django python -c "import base64, os; key=base64.urlsafe_b64decode(os.environ['RECOVERY_BACKUP_ENCRYPTION_KEY']); print(len(key))"
```

Erwartete Ausgabe:

```text
32
```
