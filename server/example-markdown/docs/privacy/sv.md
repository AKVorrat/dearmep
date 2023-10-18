# DearMEP CSAR integritetspolicy

Din integritet är viktig för oss, så vi följer vår skyldighet att informera dig om vilka av dina uppgifter vi använder på vilket sätt.

Personuppgiftsansvarig på denna instans av programvaran DearMEP är:

```
epicenter.works - Plattform Grundrechtspolitik
Linke Wienzeile 12/19
1060 Vienna, Austria
office@epicenter.works
```

Kontakt till dataskyddsombud: <dsba@epicenter.works>

Du har rätt att få information om dina personuppgifter (artikel 15 GDPR), rättelse (artikel 16 GDPR), borttagning (artikel 17 GDPR) eller begränsning av vår behandling (artikel 18 GDPR) av dina uppgifter, samt rätten att flytta din data (artikel 20 GDPR).
Förfrågningar ska skickas till  <office@epicenter.works>.
Du har även rätt att klaga till en tillsynsmyndighet, i Sverige är detta Integritetsskyddsmyndigheten (IMY) (<https://www.imy.se/>).

Vi behandlar följande personuppgifter: IP-adressen för användare av verktyget, telefonnumret för enskilda eller schemalagda samtal och potentiellt all personlig information som användaren väljer att dela via feedbackformuläret.
Vi kommer att förklara de olika fallen nedan i detalj:

## Åtkomst till webbplatsen

När DearMEP används, behandlas användarens IP-adress i vår server som befinner sig i Europa.
Syftet med behandling av IP-adresser är att förhindra missbruk och att bestämma vilket land användaren kommer ifrån för att sätta standardinställningen för landet i dialogen.
Detta händer inom serverns primärminne, och IP-adressen delas inte med tredje.
För att säkerställa tjänstens integritet och stabilitet kan vi begränsa trafiken från en IP-adress.
Därför behåller vi IP-adressen.
Trafikbegränsningen sker i serverns primärminne och gäller bara till en omstart av tjänsten. Dessutom loggar servern den nedre delen av IP-adressen (16 bitar för IPv4, 96 bitar för IPv6) så länge kampanjen pågår eller i fall av missbruk så länge som rättsliga åtgärder pågår.

Den rättsliga grunden för denna behandling är vårt berättigade intresse (art. 6.1 f i GDPR) och förpliktelser enligt lag (art. 6.1 c i GDPR).

## Användande av telefonfunktionen

När du använder vår tjänst för att ringa telefonsamtal ber vi om ditt samtycke till denna integritetspolicy för att vi ska kunna hantera ditt telefonnummer.
Vi samlar inte in eller behandlar information om innehållet i dina telefonsamtal när vårt system kopplar dig till ledamoten av Europaparlamentet.
Vi använder oss av leverantören 46Elks för att genomföra telefonsamtal.
Deras integritetspolicy gäller vid samtal och sms (<https://46elks.se/privacy-policy>).

I undantagsfall sparar vi även ytterligare data som behövs för att förhindra missbruk av tjänsten.
Detta kan innefatta IP-adresser, telefonnummer och innehåll av meddelanden.
Det kan även handla om information om icke-användare men endast i fall där missbruk ska förhindras.

Vår tjänst hanterar endast telefonnummer efter att du har gett ditt informerade samtycke till denna integritetspolicy och endast så länge det finns ett konkret syfte för behandlingen.
Den rättsliga grunden för behandlingen av telefonnummer är informerat samtycke (artikel 6.1 a i GDPR).

Vi har byggt systemet på ett sätt sätt att vi i många fall inte ens får veta ditt telefonnumer.

Vi sparar bara hash-värden (<https://sv.wikipedia.org/wiki/Hashfunktion>) av telefonnummer i vårt system för att begränsa risken för användare ifall servern komprometteras, med fyra undantag.
Telefonnummer sparas endast i klartext till den första bekräftelsen per sms eller
1) så länge användaren har en pågående prenumeration för ett samtal,
2) ett samtal har startats genom webbsidan och pågår fortfarande,
3) ett SMS med en enkät har inte skickats än (se nedan), eller
4) när det finns en rimlig misstanke om att ett nummer kan missbruka vårt system.

Det första steget i behandlingen av telefonnummer är att skicka en SMS-verifieringstoken för att bekräfta att användaren kontrollerar telefonnumret som anges i vårt system.
SMS-verifieringstoken som ännu inte har använts raderas efter högst en timme.
Vi har begränsat antalet försök som ett telefonnummer kan begära en bekräftelsetoken och därför behåller vi nummer som inte har bekräftats i ett hashat format, tillsammans med antalet försök som de har begärt en token.
Vi lagrar denna information så länge som kampanjen pågår eller, i händelse av missbruk, under eventuella efterföljande straffrättsliga åtgärder, för att förhindra att tredje parts telefonnummer spammas med bekräftelse-SMS.

Ett bekräftat telefonnummer kommer att skapa en webbtoken i en cookie för att autentisera den webbläsarsession med vilken användaren interagerar med vår tjänst.
Telefonnumret lagras i den cookie som skickas till webbläsaren på ett krypterat sätt, så att bara servern kan avkryptera det riktiga telefonnumret.
Autentiseringsinformationen lagras som en sessionskaka och raderas så snart webbläsarsessionen avslutas.

För kostnadskontroll och felsökning behåller vi anonymiserad statistisk information om användarens tid, varaktighet, destination och avkortade telefonnummer.
Vi kan dela denna anonymiserade statistik med de kampanjer som använder sig av just denna version av DearMEP för CSAR-ärendet, så att de kan bedöma verktygets inverkan på den politiska nivån.

Vid misstanke om missbruk kan vi lägga till den hashade versionen av ett telefonnummer till en spårning i vårt system.
I detta fall behålls telefonnumret i icke-hashad version när det används i vårt system igen.
Telefonnumret kommer endast att behandlas så länge som kampanjen pågår eller, i händelse av missbruk, under eventuella efterföljande straffrättsliga åtgärder (artikel 6.1 c, f i GDPR).

## Återkoppling

När ett samtal som varat över en viss tid har avslutats kommer användaren att bes om återkoppling med en unik länk till en kort enkät som är kopplad till det specifika samtalet.
Vi kan fråga efter återkopplingen direkt i webbläsaren och/eller genom ett textmeddelande med en unik länk.
Vi frågar om användaren anser sig ha lyckats övertyga politikern, om det uppstod ett tekniskt problem och ger möjlighet för ytterligare feedback.
Denna information kompletteras med vilken politiker de har ringt, användarens land och de första siffrorna i deras telefonnummer, vilket bara avslöjar deras landskod och leverantör, men inte dem som abonnent. Vi behåller en hashad version av telefonnumret för att kunna länka ihop svar som kommer från samma användare.

Återkopplingen till samtalet hålls avsiktligt pseudonymt för att möjliggöra delning av denna information med kampanjer som också implementerar denna version av DearMEP utan att avslöja någon personlig information om användarna.

I feedbackverktygets gränssnitt informeras användaren om att de måste ange kontaktuppgifter i textrutan för ytterligare feedback ifall de vill bli kontaktade av oss.
Om användaren lämnar personuppgifter som e-postadresser eller ett telefonnummer i denna textruta för feedback, förlitar vi oss på deras informerade samtycke som rättslig grund för denna behandling (artikel 6.1 a i GDPR).

## Överföring till tredje parter

Generellt delar vi inte din information till tredje part utan ditt uttryckliga samtycke.
När du använder samtalsfunktionen måste vi dela ditt telefonnummer med vår telefonleverantör 46Elks (se ovan).
När denna version av DearMEP för CSAR-lagstiftningen implementeras av kampanjer som arbetar med denna lagstiftning, kommer vi i allmänhet att ge dem tillgång till den pseudonomiserade återkopplingen (som kan innehålla personlig information som du anger i textrutan "mer återkoppling") och anonymiserad statistisk information om användningen av detta verktyg.
Du kan hitta information om de kampanjer som implementerar denna version av DearMEP på <https://dearmep.eu/showcase/chatcontrol/>.
