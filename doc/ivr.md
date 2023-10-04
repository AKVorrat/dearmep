# IVR

Dieses Dokument skizziert die möglichen Optionen des Sprachmenüs am Telefon.
Der Fokus liegt darauf, alle erforderlichen Messages zusammenzutragen, damit diese übersetzt & eingesprochen werden können.
Es handelt sich hier explizit _nicht_ um eine vollständig ausgearbeitete technische Spezifikation zur Implementierung.
Allerdings sind auch die meisten technischen Aspekte schon berücksichtigt, z.B. in Fußnoten.

**Achtung – minimal veraltet:**
Auf Basis dieses Dokumentes wurde eine CSV-Datei mit allen hier enthaltenen Texten verfasst, [`messages.csv`](ivr/messages.csv).
Diese Datei wurde außerdem um einige wenige zusätzliche Texte erweitert, die hier nicht aufgeführt sind.
**Maßgeblich ist die CSV-Datei.**
Mittels [`compile_messages.py`](ivr/compile_messages.py) können außerdem eine abgeleitete CSV-Datei, die zusätzlich die Talking Points aus der `example-config.yaml` enthält, sowie eine Excel-Datei mit dem gleichen Inhalt, erstellt werden.

Um möglichst frei formulieren zu können, wurde dieses Dokument in der Muttersprache des Autors verfasst.
Es soll noch übersetzt werden, sobald Einigkeit über die Texte besteht.

Gestrichelte Schritte stellen optionale Features dar, die nicht zwingend von Anfang an implementiert werden müssen.
Es ist allerdings sinnvoll, die entsprechenden Texte schon mit aufzuzeichnen, damit wir nicht die Sprecher\*innen später um einzelne Sätze bitten müssen.

Dargestellt ist das Hauptmenü sowie die erste Ebene.
Unterebenen, sofern vorhanden, haben kein eigenes Flowchart bekommen.

Die Zifferntasten für die Auswahl der Menüpunkte können natürlich jederzeit gedrückt werden, nicht erst wenn alle Ansagen abgespielt wurden.

Die Kästen geben einen groben Vorschlag dazu, in wie viele Audiodateien die Texte auseinandergeschnitten werden sollten.
Beispielsweise ist es sinnvoll, jede Auswahloption als eine gesonderte Datei vorzuhalten.

Der Übersichtlichkeit halber gibt es aber keine extra Kästen für Prompts, die auseinander geschnitten werden müssen, um dynamische Komponenten einzubinden.
Beispielsweise sind „Du möchtest mit [Nachname, Vorname] verbunden werden?“ zwei Dateien:
Der Teil vor dem Namen der Person, und dem Teil danach.

Zusätzlich zu den Texten in den Kästen brauchen wir als Audio

* die Wochentage (Montag, Dienstag, Mittwoch, Donnerstag, Freitag, Samstag, Sonntag)
* die Namen aller 8 Fraktionen:
  * Europäische Volkspartei (Christdemokraten)
  * Progressive Allianz der Sozialdemokraten
  * Renew Europe (Liberale)
  * Die Grünen / Europäische Freie Allianz
  * Europäische Konservative und Reformer
  * Identität und Demokratie
  * Die Linke im Europäischen Parlament
  * fraktionslos

_Wie oben vermerkt finden sich in der maßgeblichen Datei mit Textfragmenten, [`messages.csv`](ivr/messages.csv), ein paar weitere Texte._

Sprecher\*innen sollten folgende Hinweise beachten:

* Aufnahmen in 44,1 kHz 16 bit oder höher, in mono
* Audio nach der Aufzeichnung normalisieren
* Anlieferung der Dateien in unkomprimierter oder verlustfrei komprimierter Fassung, also z.B. als WAV oder FLAC
* die einzelnen Fragmente als einzelne Dateien anliefern, aber auch bitte als ungeschnittene Gesamtdatei (falls wir selbst noch Schnittarbeiten vornehmen möchten)
* Dateien bitte nicht in das Repository committen, da sie zu viel Platz brauchen; ein Nextcloud-Uploadordner kann bei Bedarf gestellt werden
* als Dateinamen für die geschnittenen Dateien bitte die „ID“ aus der Liste der Texte (CSV oder Excel) verwenden

## Hauptmenü

```mermaid
flowchart TD
    greeting["
        Hallo! Das ist ein automatisierter Anruf
        der Kampagne gegen die Chatkontrolle.¹
    "] --> callTypeCheck{Anruftyp?}

    callTypeCheck -- Instant --> instantConfirm["
        Du möchtest mit [Nachname, Vorname]
        verbunden werden? Dann drücke die 1.
    "] --> arguments

    callTypeCheck -- Scheduled --> scheduledReminder["
        Du hattest uns gebeten,
        dich zu diesem Termin anzurufen.
    "] --> scheduledConfirm["
        Wir würden dich jetzt gern mit [Nachname, Vorname]
        von der Fraktion [Name der Fraktion] verbinden.
        Wenn du damit einverstanden bist, drücke die 1.
    "] --> scheduledPostpone["
        Wenn du gerade keine Zeit hast,
        drücke die 2.
    "] --> scheduledUnsubscribe["
        Wenn du von uns zu diesem Termin in Zukunft
        nicht mehr angerufen werden möchtest,
        drücke die 3.
    "] --> arguments

    arguments["
        Wenn du zur Vorbereitung erst einmal eine
        Liste mit Argumenten hören möchtest, drücke die 5.
    "] --> optOut["
        Wenn du auf dieser Nummer nie wieder
        von uns angerufen werden möchtest,
        drücke die 9.
    "]

    classDef optional stroke-dasharray:5 10
    class scheduledPostpone,arguments,optOut optional
```

* ¹ Vielleicht gibt’s nen besseren Namen. Würde den Namen aber instanzweit halten, sprich unterschiedliche Texte je nach einbettender Website gibt’s nicht.

## 1: Verbinden

```mermaid
flowchart TD
    start((1)) --> busyCheck{"
        Laut System
        (inzwischen)
        bereits im Call?
    "}

    busyCheck -- ja --> unavailable["
        Diese Person ist aktuell
        anscheinend bereits im Gespräch.
    "] --> alternativeCheck

    alternativeCheck{"
        Alternativvorschlag
        vorhanden?²
    "}

    alternativeCheck -- ja --> alternative["
        Dürfen wir dich stattdessen
        mit [Nachname, Vorname] von
        der Fraktion [Fraktion] verbinden?
        Dann drücke die 1.
        Ansonsten drücke die 2.
    "] -- drückt 1 --> toStart(("
        zurück
        zu 1
    "))
    alternative -- drückt 2 --> callType

    alternativeCheck -- nein --> noAlternative["
        Aktuell können wir dir leider
        niemand anderen anbieten.
    "] --> callType{Anruftyp}

    callType -- Instant --> tryAgain["
        Bitte versuche es
        später noch einmal,
        oder wähle auf unserer Website
        jemand anderen aus.
    "] --> hangUp["Bis bald!"]
    callType -- Scheduled --> willRetry["
        Wir werden dich zum
        nächsten vereinbarten Termin
        erneut anrufen.
    "] --> hangUp

    busyCheck -- nein --> connecting["
        Alles klar! Wir verbinden dich.
        Einen Moment bitte. Dein Gespräch
        wird selbstverständlich
        nicht aufgezeichnet.¹
    "]
```

* ¹ Expliziter Hinweis, weil IVR-eingeleitete Gespräche häufig aufgezeichnet werden.
* ² Dieser Check wird maximal 2× im Gespräch ausgeführt. Beim dritten Mal schlägt er automatisch fehl, damit die Userin nicht ewig in einer Schleife hängt.

## 2: keine Zeit

```mermaid
flowchart TD
    start((2)) --> alreadyPostponedCheck{"
        wurde bereits
        verschoben?¹
    "} -- nein --> postponePrompt["
        Sollen wir dich in etwa einer Viertelstunde
        nochmal anrufen? Dann drücke die 1.
    "] --> othersConfiguredCheck

    alreadyPostponedCheck -- ja --> othersConfiguredCheck

    othersConfiguredCheck{"
        andere
        konfiguriert?²
    "} -- ja --> otherPrompt

    othersConfiguredCheck -- nein --> nextWeekPrompt

    otherPrompt["
        Wenn wir uns erst wie geplant am
        [Wochentag] wieder melden sollen,
        drücke die 2 oder lege einfach auf.
    "] --> deletePrompt

    nextWeekPrompt["
        Wenn wir uns einfach nächste Woche
        wieder melden sollen, drücke die 2
        oder lege einfach auf.
    "] --> deletePrompt

    deletePrompt["
        Wenn du nicht mehr jeden [heutiger Wochentag]
        angerufen werden möchtest, drücke die 3.
    "]

    deletePrompt -- "drückt 1³" --> postpone["
        Alles klar, bis gleich!
    "]
    deletePrompt -- "drückt 2" --> next["
        So machen wir’s. Bis dann!
    "]
    deletePrompt -- "drückt 3" --> delete((zu 3))
```

* ¹ Damit der Anruf nicht ewig „gesnoozed“ werden kann und wir dieselbe Userin alle 15 Minuten anrufen, ist diese Funktion auf einmaliges Verschieben begrenzt.
* ² Das Prompt ändert sich, je nachdem, ob noch andere Termine gescheduled sind. Die Funktionalität bleibt dieselbe: Der Anruf wird einfach beendet und zum nächsten Termin wieder angerufen. Einfach aufzulegen statt die 2 zu drücken hätte denselben Effekt.
* ³ Nur verfügbar, wenn nicht schon einmal verschoben wurde.

## 3: Termin löschen

```mermaid
flowchart TD
    start((3)) --> othersCheck{"
        andere
        konfiguriert?
    "}

    othersCheck -- nein --> allDeleted

    othersCheck -- ja --> othersMessage["
        Du hast noch mindestens einen
        anderen wöchentlichen Termin
        bei uns hinterlegt.
    "] --> deleteAllPrompt["
        Wenn wir alle deine
        Anruftermine löschen sollen,
        drücke die 1. Wenn wir nur
        den Termin jeden [Wochentag]
        löschen sollen, drücke die 2.
    "] -- drückt 1 --> allDeleted["
        Alles klar. Du wirst in Zukunft
        nicht mehr automatisch
        von uns angerufen. Wenn du
        automatische Anrufe wieder
        aktivieren möchtest, kannst du
        das über unsere Website tun.
    "] --> bye[Bis bald!]

    deleteAllPrompt -- drückt 2 --> weekdayDeleted["
        Alles klar. Wir werden dich am
        [Wochentag] nicht mehr automatisch
        anrufen. Andere konfigurierte
        Termine bleiben bestehen. Du kannst
        sie über unsere Website einsehen,
        anpassen, oder löschen.
    "] --> bye
```

## 5: Argumente

```mermaid
flowchart TD
    start((5)) --> introMessage["
        Okay. Hier sind ein paar Argumente
        gegen die Chatkontrolle.¹
    "] --> cancelInstructions["
        Du kannst jederzeit die 1 drücken,
        um von uns direkt mit [Name, Vorname]
        verbunden zu werden.
    "] --> arguments[["[…Argumente…]"]] --> continuePrompt["
        Alles klar? Dann drücke jetzt die 1,
        um verbunden zu werden.²
    "] --> continue((zu 1))
```

* ¹ Dieser Text sollte von der jeweiligen Instanz angepasst werden, genauso wie die Argumente natürlich.
* ² Wenn nicht reagiert wird, nur diese Nachricht loopen, nicht die kompletten Argumente.

## 9: Blockliste

_Wird initial noch nicht implementiert, aber die Texte aufzuzeichnen macht Sinn._

```mermaid
flowchart TD
    start((9)) --> confirmBlocklistPrompt["
        Bist du sicher? Wir würden deine Nummer
        auf unsere interne Blockliste setzen. Du wirst
        dann nicht mehr zu automatisierten Terminen
        angerufen und kannst auch nicht mehr über unsere Website
        direkt Anrufe zu Abgeordneten aufbauen. Du müsstest
        uns eine E-Mail schreiben, falls du von der Blockliste
        jemals wieder entfernt werden möchtest. Drück die 9,
        wenn wir dich auf diese Blockliste setzen sollen.
    "] --> scheduledCheck{"Anruftyp?"} -- Scheduled --> deleteScheduledPrompt["
        Wenn du hingegen einfach nur nicht mehr
        jeden [heutiger Wochentag] von uns angerufen
        werden möchtest, drücke die 3.
    "] --> mainMenuPrompt["
        Oder drücke die 0, um zurück
        ins Hauptmenü zu kommen.
    "]

    scheduledCheck -- Instant --> mainMenuPrompt

    mainMenuPrompt -- drückt 9 --> blocked["
        Alles klar. Sorry für die Störung, und
        hab noch einen schönen Tag.
    "]

    mainMenuPrompt -- "drückt 3¹" --> delete((zu 3))

    mainMenuPrompt -- drückt 0 --> mainMenu(("
        zum
        Hauptmenü
    "))
```

* ¹ steht nur zur Verfügung wenn Scheduled
