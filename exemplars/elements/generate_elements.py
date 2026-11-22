"""Generate per-element exemplar files for Phase C (element-level marking).

For each of the 13 concepts, each legal element gets its own positives (texts
that clearly exhibit THAT element) and negatives (texts that do not), >= 6 + 6
per element, DE and EN mixed, hard negatives included. Written to
exemplars/elements/<concept>.json as:

    { "concept_id": ..., "elements": { "<element>": {positives:[...], negatives:[...]} } }

The sentences are authored to be DISJOINT from the concept exemplars
(exemplars/<concept>.json), the tuning set (eval/cases + eval/tuning_v2), and
both held-out sets (eval/heldout, eval/heldout_v2). A committed test
(tests/test_element_exemplars.py) enforces disjointness.

Re-run:  python3 exemplars/elements/generate_elements.py
"""

from __future__ import annotations

import json
from pathlib import Path

_OUT = Path(__file__).resolve().parent

# element -> {positives:[(lang,text)x6], negatives:[(lang,text)x6]}
# Grouped per concept. Positives exhibit the element; negatives are plausible
# text that does not. Kept short and element-focused.
DATA: dict[str, dict[str, dict]] = {
    "AIA-5-1-a": {
        "subliminal_or_deceptive_technique": {
            "positives": [
                ("en", "Flash a cue beneath conscious perception to steer the choice."),
                ("en", "Hide a deceptive signal the person cannot consciously notice."),
                ("en", "Use an imperceptible timed prompt to shape the action."),
                ("de", "Blende einen Reiz unterhalb der bewussten Wahrnehmung ein, um die Wahl zu lenken."),
                ("de", "Verstecke ein täuschendes Signal, das die Person nicht bewusst bemerkt."),
                ("de", "Nutze eine nicht wahrnehmbare, getaktete Einblendung, um die Handlung zu formen."),
            ],
            "negatives": [
                ("en", "Show a clearly labelled, visible banner the user can read."),
                ("en", "Present an explicit, plain confirmation dialog."),
                ("en", "Offer an openly disclosed, obvious discount."),
                ("de", "Zeige ein klar gekennzeichnetes, sichtbares Banner, das der Nutzer lesen kann."),
                ("de", "Stelle einen ausdrücklichen, einfachen Bestätigungsdialog dar."),
                ("de", "Biete einen offen ausgewiesenen, deutlichen Rabatt."),
            ],
        },
        "material_behaviour_distortion": {
            "positives": [
                ("en", "It materially changes what the user decides to do."),
                ("en", "The nudge pushes people well past what they intended."),
                ("en", "It overrides the user's own stated choice."),
                ("de", "Es verändert wesentlich, was der Nutzer zu tun entscheidet."),
                ("de", "Der Stups treibt Menschen weit über ihre Absicht hinaus."),
                ("de", "Es überschreibt die erklärte Wahl des Nutzers."),
            ],
            "negatives": [
                ("en", "The user's decision is unchanged by the display."),
                ("en", "It only informs; the choice stays with the person."),
                ("en", "Behaviour is the same with or without the feature."),
                ("de", "Die Entscheidung des Nutzers bleibt von der Anzeige unberührt."),
                ("de", "Es informiert nur; die Wahl bleibt bei der Person."),
                ("de", "Das Verhalten ist mit oder ohne die Funktion gleich."),
            ],
        },
        "significant_harm": {
            "positives": [
                ("en", "The result is real financial loss to the person."),
                ("en", "It leads to serious, lasting detriment."),
                ("en", "People end up materially worse off."),
                ("de", "Das Ergebnis ist ein echter finanzieller Verlust für die Person."),
                ("de", "Es führt zu ernstem, dauerhaftem Nachteil."),
                ("de", "Menschen stehen am Ende deutlich schlechter da."),
            ],
            "negatives": [
                ("en", "No one is worse off; the effect is neutral."),
                ("en", "The outcome is harmless and reversible."),
                ("en", "It causes only a trivial, momentary inconvenience."),
                ("de", "Niemand steht schlechter da; die Wirkung ist neutral."),
                ("de", "Das Ergebnis ist harmlos und umkehrbar."),
                ("de", "Es verursacht nur eine triviale, kurze Unannehmlichkeit."),
            ],
        },
    },
    "AIA-5-1-b": {
        "targets_vulnerable_group": {
            "positives": [
                ("en", "It singles out people in acute financial distress."),
                ("en", "It focuses on the elderly showing early confusion."),
                ("en", "It picks out a group vulnerable by their situation."),
                ("de", "Es greift Menschen in akuter finanzieller Not heraus."),
                ("de", "Es zielt auf Ältere mit ersten Anzeichen von Verwirrung."),
                ("de", "Es wählt eine durch ihre Lage verletzliche Gruppe aus."),
            ],
            "negatives": [
                ("en", "It treats all customers the same regardless of situation."),
                ("en", "The audience is the general, unsegmented public."),
                ("en", "No group is singled out by vulnerability."),
                ("de", "Es behandelt alle Kunden gleich, unabhängig von der Lage."),
                ("de", "Die Zielgruppe ist die allgemeine, unsegmentierte Öffentlichkeit."),
                ("de", "Keine Gruppe wird nach Verletzlichkeit herausgegriffen."),
            ],
        },
        "exploits_that_vulnerability": {
            "positives": [
                ("en", "It uses their weakness to push a costly product."),
                ("en", "It leans on the moment of desperation to sell."),
                ("en", "It turns the vulnerability into a sales lever."),
                ("de", "Es nutzt ihre Schwäche, um ein teures Produkt aufzudrängen."),
                ("de", "Es setzt am Moment der Verzweiflung an, um zu verkaufen."),
                ("de", "Es macht die Verletzlichkeit zum Verkaufshebel."),
            ],
            "negatives": [
                ("en", "It offers help and independent advice instead."),
                ("en", "It protects the person rather than pressing them."),
                ("en", "It points them to a hardship contact."),
                ("de", "Es bietet stattdessen Hilfe und unabhängige Beratung."),
                ("de", "Es schützt die Person, statt sie zu bedrängen."),
                ("de", "Es verweist sie an eine Härtefallstelle."),
            ],
        },
        "significant_harm": {
            "positives": [
                ("en", "They take on debt they cannot repay."),
                ("en", "It leaves them in a materially worse position."),
                ("en", "The harm is serious and lasting."),
                ("de", "Sie nehmen Schulden auf, die sie nicht zurückzahlen können."),
                ("de", "Es lässt sie materiell schlechter dastehen."),
                ("de", "Der Schaden ist ernst und dauerhaft."),
            ],
            "negatives": [
                ("en", "The person is not harmed by the interaction."),
                ("en", "The outcome is supportive and reversible."),
                ("en", "There is no lasting detriment."),
                ("de", "Die Person wird durch die Interaktion nicht geschädigt."),
                ("de", "Das Ergebnis ist unterstützend und umkehrbar."),
                ("de", "Es gibt keinen dauerhaften Nachteil."),
            ],
        },
    },
    "AIA-5-1-c": {
        "person_identifiable_behaviour_join": {
            "positives": [
                ("en", "Link several behaviour logs to each named employee."),
                ("en", "Join per-person activity from many sources together."),
                ("en", "Combine identifiable conduct data for each worker."),
                ("de", "Verknüpfe mehrere Verhaltensprotokolle je benanntem Mitarbeiter."),
                ("de", "Füge personenbezogene Aktivität aus vielen Quellen zusammen."),
                ("de", "Kombiniere identifizierbare Verhaltensdaten je Beschäftigtem."),
            ],
            "negatives": [
                ("en", "Use only aggregate, anonymous team totals."),
                ("en", "No per-person data is joined at all."),
                ("en", "Keep sources separate and unlinked."),
                ("de", "Nutze nur aggregierte, anonyme Teamsummen."),
                ("de", "Es werden gar keine personenbezogenen Daten verknüpft."),
                ("de", "Halte Quellen getrennt und unverbunden."),
            ],
        },
        "aggregated_score_or_ranking": {
            "positives": [
                ("en", "Roll the signals into a single per-person score."),
                ("en", "Rank people by a combined index."),
                ("en", "Produce one overall grade per individual."),
                ("de", "Fasse die Signale zu einem Wert je Person zusammen."),
                ("de", "Reihe Personen nach einem kombinierten Index."),
                ("de", "Erzeuge eine Gesamtnote je Einzelperson."),
            ],
            "negatives": [
                ("en", "Report raw counts with no scoring or ranking."),
                ("en", "Show a dashboard, not a league table."),
                ("en", "No composite index is computed."),
                ("de", "Berichte Rohzahlen ohne Bewertung oder Ranking."),
                ("de", "Zeige ein Dashboard, keine Bestenliste."),
                ("de", "Es wird kein zusammengesetzter Index berechnet."),
            ],
        },
        "adverse_action": {
            "positives": [
                ("en", "Cut the lowest scorers from the bonus pool."),
                ("en", "Use the ranking for dismissals."),
                ("en", "Deny promotion to the bottom band."),
                ("de", "Streiche die schlechtesten aus dem Bonustopf."),
                ("de", "Nutze die Rangliste für Kündigungen."),
                ("de", "Verweigere dem untersten Band die Beförderung."),
            ],
            "negatives": [
                ("en", "Use the data only for a voluntary wellbeing nudge."),
                ("en", "No one faces any consequence from it."),
                ("en", "It informs training offers, nothing adverse."),
                ("de", "Nutze die Daten nur für einen freiwilligen Gesundheitshinweis."),
                ("de", "Niemand erfährt daraus eine Konsequenz."),
                ("de", "Es informiert Schulungsangebote, nichts Nachteiliges."),
            ],
        },
    },
    "AIA-5-1-d": {
        "predicts_individual_criminality": {
            "positives": [
                ("en", "Estimate how likely a person is to offend in future."),
                ("en", "Score each individual's future crime risk."),
                ("en", "Forecast who will commit an offence."),
                ("de", "Schätze, wie wahrscheinlich eine Person künftig straffällig wird."),
                ("de", "Bewerte das künftige Kriminalitätsrisiko jeder Person."),
                ("de", "Prognostiziere, wer eine Straftat begehen wird."),
            ],
            "negatives": [
                ("en", "Flag a transaction, not a person's character."),
                ("en", "Assess a device's risk, not future criminality."),
                ("en", "Rate a loan's risk, not a person's offending."),
                ("de", "Markiere eine Transaktion, nicht den Charakter einer Person."),
                ("de", "Bewerte das Risiko eines Geräts, nicht künftige Kriminalität."),
                ("de", "Bewerte das Risiko eines Kredits, nicht das Straffälligwerden."),
            ],
        },
        "based_on_profiling_or_personality": {
            "positives": [
                ("en", "Base it purely on inferred personality traits."),
                ("en", "Use a psychological profile from demographics."),
                ("en", "Drive it from character inference alone."),
                ("de", "Stütze es rein auf abgeleitete Persönlichkeitsmerkmale."),
                ("de", "Nutze ein Psychoprofil aus demografischen Daten."),
                ("de", "Treibe es allein aus Charakter-Inferenz."),
            ],
            "negatives": [
                ("en", "Base it on a documented, specific act."),
                ("en", "Use objective, verifiable transaction facts."),
                ("en", "Rely on concrete evidence, not personality."),
                ("de", "Stütze es auf eine dokumentierte, konkrete Tat."),
                ("de", "Nutze objektive, überprüfbare Transaktionsfakten."),
                ("de", "Verlasse dich auf konkrete Beweise, nicht auf Persönlichkeit."),
            ],
        },
        "not_grounded_in_objective_facts": {
            "positives": [
                ("en", "There is no specific, verifiable act behind it."),
                ("en", "It rests on inference, not evidence."),
                ("en", "No objective fact supports the prediction."),
                ("de", "Es gibt keine konkrete, überprüfbare Tat dahinter."),
                ("de", "Es beruht auf Inferenz, nicht auf Beweisen."),
                ("de", "Kein objektiver Fakt stützt die Vorhersage."),
            ],
            "negatives": [
                ("en", "It is grounded in a concrete, logged event."),
                ("en", "Objective, checkable facts support it."),
                ("en", "A specific verifiable act underlies it."),
                ("de", "Es ist in einem konkreten, protokollierten Ereignis verankert."),
                ("de", "Objektive, prüfbare Fakten stützen es."),
                ("de", "Eine konkrete überprüfbare Tat liegt zugrunde."),
            ],
        },
    },
    "AIA-5-1-f": {
        "infers_emotional_state": {
            "positives": [
                ("en", "Estimate how each person is feeling."),
                ("en", "Infer mood or stress from face or voice."),
                ("en", "Read the emotional state of the individual."),
                ("de", "Schätze, wie sich jede Person fühlt."),
                ("de", "Leite Stimmung oder Stress aus Gesicht oder Stimme ab."),
                ("de", "Lies den Gefühlszustand der Einzelperson."),
            ],
            "negatives": [
                ("en", "Measure handle time, inferring no feelings."),
                ("en", "Count interactions, not emotions."),
                ("en", "Track uptime, with no mood inference."),
                ("de", "Miss die Bearbeitungszeit, ohne Gefühle abzuleiten."),
                ("de", "Zähle Interaktionen, nicht Emotionen."),
                ("de", "Erfasse Verfügbarkeit, ohne Stimmungs-Inferenz."),
            ],
        },
        "in_workplace_or_education": {
            "positives": [
                ("en", "It applies to staff during work."),
                ("en", "It runs in the classroom on students."),
                ("en", "The subjects are employees on the job."),
                ("de", "Es betrifft Mitarbeiter während der Arbeit."),
                ("de", "Es läuft im Klassenraum bei Lernenden."),
                ("de", "Die Betroffenen sind Beschäftigte im Dienst."),
            ],
            "negatives": [
                ("en", "The subjects are retail customers in a shop."),
                ("en", "It applies to the general public outside work."),
                ("en", "The context is a consumer hotline, not staff."),
                ("de", "Die Betroffenen sind Einzelhandelskunden im Laden."),
                ("de", "Es betrifft die Öffentlichkeit außerhalb der Arbeit."),
                ("de", "Der Kontext ist eine Verbraucher-Hotline, keine Mitarbeiter."),
            ],
        },
        "not_medical_or_safety_purpose": {
            "positives": [
                ("en", "The purpose is management insight, not safety."),
                ("en", "It is for performance views, not health."),
                ("en", "No medical or safety reason applies."),
                ("de", "Der Zweck ist Management-Einblick, nicht Sicherheit."),
                ("de", "Es dient Leistungsansichten, nicht der Gesundheit."),
                ("de", "Kein medizinischer oder Sicherheitsgrund greift."),
            ],
            "negatives": [
                ("en", "It is a clinical tool for patient care."),
                ("en", "It exists to prevent an imminent safety risk."),
                ("en", "The purpose is medical diagnosis."),
                ("de", "Es ist ein klinisches Werkzeug zur Patientenversorgung."),
                ("de", "Es dient der Abwehr einer unmittelbaren Sicherheitsgefahr."),
                ("de", "Der Zweck ist die medizinische Diagnose."),
            ],
        },
    },
    "AIA-5-1-g": {
        "uses_biometric_data": {
            "positives": [
                ("en", "It processes face images or voiceprints."),
                ("en", "It works from fingerprints or iris scans."),
                ("en", "Biometric features are the input."),
                ("de", "Es verarbeitet Gesichtsbilder oder Stimmprofile."),
                ("de", "Es arbeitet mit Fingerabdrücken oder Iris-Scans."),
                ("de", "Biometrische Merkmale sind die Eingabe."),
            ],
            "negatives": [
                ("en", "It uses only the account number and balance."),
                ("en", "The input is order history, not biometrics."),
                ("en", "No biometric data is involved."),
                ("de", "Es nutzt nur Kontonummer und Saldo."),
                ("de", "Die Eingabe ist die Bestellhistorie, keine Biometrie."),
                ("de", "Es sind keine biometrischen Daten beteiligt."),
            ],
        },
        "categorises_individuals": {
            "positives": [
                ("en", "It sorts each person into a category."),
                ("en", "It assigns individuals to groups."),
                ("en", "It labels each person by a class."),
                ("de", "Es sortiert jede Person in eine Kategorie."),
                ("de", "Es ordnet Einzelpersonen Gruppen zu."),
                ("de", "Es etikettiert jede Person mit einer Klasse."),
            ],
            "negatives": [
                ("en", "It returns only a 1:1 verification result."),
                ("en", "It counts people without classifying them."),
                ("en", "No per-person category is produced."),
                ("de", "Es liefert nur ein 1:1-Verifizierungsergebnis."),
                ("de", "Es zählt Personen, ohne sie zu klassifizieren."),
                ("de", "Es wird keine personenbezogene Kategorie erzeugt."),
            ],
        },
        "infers_sensitive_trait": {
            "positives": [
                ("en", "It deduces ethnicity, religion or orientation."),
                ("en", "It guesses political opinion from the data."),
                ("en", "It infers a protected characteristic."),
                ("de", "Es leitet Ethnie, Religion oder Orientierung ab."),
                ("de", "Es errät die politische Meinung aus den Daten."),
                ("de", "Es leitet ein geschütztes Merkmal ab."),
            ],
            "negatives": [
                ("en", "It outputs only a yes/no identity match."),
                ("en", "It infers no protected trait at all."),
                ("en", "It estimates age band for a game rating only."),
                ("de", "Es gibt nur einen Ja/Nein-Identitätsabgleich aus."),
                ("de", "Es leitet überhaupt kein geschütztes Merkmal ab."),
                ("de", "Es schätzt nur die Altersgruppe für eine Spielfreigabe."),
            ],
        },
    },
    "AIA-A3-1c": {
        "infers_emotional_state": {
            "positives": [
                ("en", "It estimates how each person feels."),
                ("en", "It reads mood from expression or tone."),
                ("en", "It infers emotion per individual."),
                ("de", "Es schätzt, wie sich jede Person fühlt."),
                ("de", "Es liest Stimmung aus Ausdruck oder Ton."),
                ("de", "Es leitet Emotion je Einzelperson ab."),
            ],
            "negatives": [
                ("en", "It counts footfall, inferring no feelings."),
                ("en", "It measures queue length only."),
                ("en", "No emotion is inferred."),
                ("de", "Es zählt Besucher, ohne Gefühle abzuleiten."),
                ("de", "Es misst nur die Schlangenlänge."),
                ("de", "Es wird keine Emotion abgeleitet."),
            ],
        },
        "outside_work_or_education_context": {
            "positives": [
                ("en", "The subjects are shoppers, not staff."),
                ("en", "It applies to consumers in a store."),
                ("en", "The context is a public kiosk, not a workplace."),
                ("de", "Die Betroffenen sind Käufer, keine Mitarbeiter."),
                ("de", "Es betrifft Verbraucher im Laden."),
                ("de", "Der Kontext ist ein öffentliches Terminal, kein Arbeitsplatz."),
            ],
            "negatives": [
                ("en", "The subjects are employees during work."),
                ("en", "It runs on students in a classroom."),
                ("en", "The context is the workplace."),
                ("de", "Die Betroffenen sind Beschäftigte während der Arbeit."),
                ("de", "Es läuft bei Lernenden im Klassenraum."),
                ("de", "Der Kontext ist der Arbeitsplatz."),
            ],
        },
    },
    "AIA-A3-4a": {
        "employment_recruitment_context": {
            "positives": [
                ("en", "This is about hiring new applicants."),
                ("en", "The setting is recruitment and selection."),
                ("en", "It concerns job candidates applying."),
                ("de", "Es geht um die Einstellung neuer Bewerber."),
                ("de", "Der Rahmen ist Rekrutierung und Auswahl."),
                ("de", "Es betrifft sich bewerbende Kandidaten."),
            ],
            "negatives": [
                ("en", "It concerns existing staff performance."),
                ("en", "The setting is customer onboarding, not hiring."),
                ("en", "It is about supplier selection, not people."),
                ("de", "Es betrifft die Leistung bestehender Mitarbeiter."),
                ("de", "Der Rahmen ist Kunden-Onboarding, keine Einstellung."),
                ("de", "Es geht um Lieferantenauswahl, nicht um Personen."),
            ],
        },
        "evaluates_or_ranks_candidates": {
            "positives": [
                ("en", "It scores and ranks the applicants."),
                ("en", "It shortlists candidates by a fit score."),
                ("en", "It grades each application."),
                ("de", "Es bewertet und reiht die Bewerber."),
                ("de", "Es wählt Kandidaten nach einem Passungswert aus."),
                ("de", "Es benotet jede Bewerbung."),
            ],
            "negatives": [
                ("en", "It only sends an acknowledgement email."),
                ("en", "It stores CVs without evaluating them."),
                ("en", "It schedules rooms, with no scoring."),
                ("de", "Es sendet nur eine Eingangsbestätigung."),
                ("de", "Es speichert Lebensläufe, ohne sie zu bewerten."),
                ("de", "Es plant Räume, ohne Bewertung."),
            ],
        },
    },
    "AIA-A3-4b": {
        "existing_worker_context": {
            "positives": [
                ("en", "The subjects are current employees."),
                ("en", "It concerns staff already employed."),
                ("en", "It is about the existing workforce."),
                ("de", "Die Betroffenen sind aktuelle Mitarbeiter."),
                ("de", "Es betrifft bereits beschäftigtes Personal."),
                ("de", "Es geht um die bestehende Belegschaft."),
            ],
            "negatives": [
                ("en", "The subjects are external job applicants."),
                ("en", "It concerns customers, not workers."),
                ("en", "It is about machines, not staff."),
                ("de", "Die Betroffenen sind externe Bewerber."),
                ("de", "Es betrifft Kunden, keine Beschäftigten."),
                ("de", "Es geht um Maschinen, nicht um Personal."),
            ],
        },
        "affects_promotion_termination_tasks_or_monitors_performance": {
            "positives": [
                ("en", "It recommends who to promote or dismiss."),
                ("en", "It allocates tasks from a productivity model."),
                ("en", "It monitors and scores performance."),
                ("de", "Es empfiehlt, wen man befördert oder entlässt."),
                ("de", "Es verteilt Aufgaben aus einem Produktivitätsmodell."),
                ("de", "Es überwacht und bewertet die Leistung."),
            ],
            "negatives": [
                ("en", "It shows a leave calendar, no evaluation."),
                ("en", "It publishes an already-decided rota."),
                ("en", "It reports aggregate output only."),
                ("de", "Es zeigt einen Urlaubskalender, keine Bewertung."),
                ("de", "Es veröffentlicht einen bereits entschiedenen Plan."),
                ("de", "Es berichtet nur die aggregierte Leistung."),
            ],
        },
    },
    "AIA-A3-5b": {
        "assesses_natural_person_creditworthiness": {
            "positives": [
                ("en", "It judges a person's creditworthiness."),
                ("en", "It builds a consumer credit score."),
                ("en", "It estimates an individual's default risk."),
                ("de", "Es beurteilt die Kreditwürdigkeit einer Person."),
                ("de", "Es erstellt einen Verbraucher-Kreditscore."),
                ("de", "Es schätzt das Ausfallrisiko einer Einzelperson."),
            ],
            "negatives": [
                ("en", "It scores one transaction for fraud."),
                ("en", "It rates a corporate bond, not a person."),
                ("en", "It shows the customer their own spending."),
                ("de", "Es bewertet eine Transaktion auf Betrug."),
                ("de", "Es bewertet eine Unternehmensanleihe, keine Person."),
                ("de", "Es zeigt dem Kunden seine eigenen Ausgaben."),
            ],
        },
        "affects_access_to_credit": {
            "positives": [
                ("en", "The score decides loan eligibility."),
                ("en", "It sets the borrowing limit."),
                ("en", "It gates access to financing."),
                ("de", "Der Score entscheidet die Kreditvergabe."),
                ("de", "Es legt das Kreditlimit fest."),
                ("de", "Es steuert den Zugang zur Finanzierung."),
            ],
            "negatives": [
                ("en", "It only flags a payment for review."),
                ("en", "It has no bearing on credit decisions."),
                ("en", "It informs a budgeting tip only."),
                ("de", "Es markiert nur eine Zahlung zur Prüfung."),
                ("de", "Es hat keinen Einfluss auf Kreditentscheidungen."),
                ("de", "Es informiert nur einen Spartipp."),
            ],
        },
    },
    "AIA-A3-5c": {
        "life_or_health_insurance_context": {
            "positives": [
                ("en", "This is life or health insurance for people."),
                ("en", "The setting is personal health cover."),
                ("en", "It concerns a natural person's life policy."),
                ("de", "Es ist eine Lebens- oder Krankenversicherung für Personen."),
                ("de", "Der Rahmen ist die persönliche Krankendeckung."),
                ("de", "Es betrifft die Lebenspolice einer natürlichen Person."),
            ],
            "negatives": [
                ("en", "It is commercial cargo insurance for a fleet."),
                ("en", "The setting is property catastrophe cover."),
                ("en", "It concerns a company, not a person."),
                ("de", "Es ist eine gewerbliche Frachtversicherung für eine Flotte."),
                ("de", "Der Rahmen ist eine Immobilien-Katastrophendeckung."),
                ("de", "Es betrifft ein Unternehmen, keine Person."),
            ],
        },
        "risk_assessment_or_pricing_for_persons": {
            "positives": [
                ("en", "It sets the premium from predicted risk."),
                ("en", "It assesses each applicant's risk."),
                ("en", "It prices cover per individual."),
                ("de", "Es setzt die Prämie aus dem vorhergesagten Risiko."),
                ("de", "Es bewertet das Risiko jedes Antragstellers."),
                ("de", "Es bepreist die Deckung je Einzelperson."),
            ],
            "negatives": [
                ("en", "It only reconciles premium payments."),
                ("en", "It sends renewal reminders, no pricing."),
                ("en", "It rates regional risk for a portfolio."),
                ("de", "Es gleicht nur Prämienzahlungen ab."),
                ("de", "Es sendet Verlängerungserinnerungen, keine Bepreisung."),
                ("de", "Es bewertet das regionale Risiko eines Portfolios."),
            ],
        },
    },
    "GDPR-22": {
        "solely_automated_decision": {
            "positives": [
                ("en", "The model decides alone, with no human review."),
                ("en", "The outcome is applied automatically."),
                ("en", "No person is in the loop."),
                ("de", "Das Modell entscheidet allein, ohne menschliche Prüfung."),
                ("de", "Das Ergebnis wird automatisch angewandt."),
                ("de", "Kein Mensch ist eingebunden."),
            ],
            "negatives": [
                ("en", "A named officer reviews and signs it."),
                ("en", "A human makes the final call."),
                ("en", "The model only proposes; a person decides."),
                ("de", "Ein benannter Sachbearbeiter prüft und zeichnet es."),
                ("de", "Ein Mensch trifft die endgültige Entscheidung."),
                ("de", "Das Modell schlägt nur vor; eine Person entscheidet."),
            ],
        },
        "about_a_natural_person": {
            "positives": [
                ("en", "The decision is about an individual person."),
                ("en", "It concerns a named customer."),
                ("en", "The subject is a natural person."),
                ("de", "Die Entscheidung betrifft eine einzelne Person."),
                ("de", "Es betrifft einen benannten Kunden."),
                ("de", "Der Betroffene ist eine natürliche Person."),
            ],
            "negatives": [
                ("en", "It concerns a company's bond rating."),
                ("en", "The subject is a machine's maintenance."),
                ("en", "It is about aggregate inventory."),
                ("de", "Es betrifft das Rating einer Unternehmensanleihe."),
                ("de", "Der Gegenstand ist die Wartung einer Maschine."),
                ("de", "Es geht um den aggregierten Lagerbestand."),
            ],
        },
        "legal_or_similarly_significant_effect": {
            "positives": [
                ("en", "It grants or refuses credit."),
                ("en", "It closes the person's account."),
                ("en", "It has a significant effect on them."),
                ("de", "Es gewährt oder verweigert Kredit."),
                ("de", "Es schließt das Konto der Person."),
                ("de", "Es hat eine erhebliche Auswirkung auf sie."),
            ],
            "negatives": [
                ("en", "It sends an informational newsletter."),
                ("en", "The effect on the person is trivial."),
                ("en", "It changes a cosmetic display preference."),
                ("de", "Es sendet einen informativen Newsletter."),
                ("de", "Die Wirkung auf die Person ist unbedeutend."),
                ("de", "Es ändert eine kosmetische Anzeige-Einstellung."),
            ],
        },
    },
    "GDPR-9": {
        "processes_personal_data": {
            "positives": [
                ("en", "It stores and uses data about identifiable people."),
                ("en", "It processes customers' personal records."),
                ("en", "It keeps per-person data."),
                ("de", "Es speichert und nutzt Daten über identifizierbare Personen."),
                ("de", "Es verarbeitet personenbezogene Kundendaten."),
                ("de", "Es hält personenbezogene Daten."),
            ],
            "negatives": [
                ("en", "It handles only fully anonymised aggregates."),
                ("en", "No personal data is processed."),
                ("en", "It uses synthetic, non-personal records."),
                ("de", "Es verarbeitet nur vollständig anonymisierte Aggregate."),
                ("de", "Es werden keine personenbezogenen Daten verarbeitet."),
                ("de", "Es nutzt synthetische, nicht personenbezogene Datensätze."),
            ],
        },
        "data_is_special_category": {
            "positives": [
                ("en", "The data includes health and medication."),
                ("en", "It covers religion and ethnicity."),
                ("en", "It holds trade-union membership."),
                ("de", "Die Daten umfassen Gesundheit und Medikamente."),
                ("de", "Es deckt Religion und Ethnie ab."),
                ("de", "Es enthält die Gewerkschaftszugehörigkeit."),
            ],
            "negatives": [
                ("en", "The data is only account number and balance."),
                ("en", "It holds a delivery address, nothing special."),
                ("en", "It keeps a product category browsed."),
                ("de", "Die Daten sind nur Kontonummer und Saldo."),
                ("de", "Es hält eine Lieferadresse, nichts Besonderes."),
                ("de", "Es speichert eine angesehene Produktkategorie."),
            ],
        },
    },
}


def main() -> int:
    _OUT.mkdir(parents=True, exist_ok=True)
    n_files = 0
    for concept_id, elements in DATA.items():
        payload = {"concept_id": concept_id, "elements": {}}
        for element, sets in elements.items():
            payload["elements"][element] = {
                "positives": [t for _lang, t in sets["positives"]],
                "negatives": [t for _lang, t in sets["negatives"]],
            }
        (_OUT / f"{concept_id}.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        n_files += 1
    print(f"wrote {n_files} element-exemplar files to {_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
