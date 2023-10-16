# DearMEP CSAR Privacy Policy

Your privacy is important to us, so we take our duty to inform you which of your data we use in which way very seriously.

Responsible entity for the processing of this instance of the DearMEP software:

```
epicenter.works - Plattform Grundrechtspolitik
Linke Wienzeile 12/19
1060 Vienna, Austria
office@epicenter.works
```

Contact information of the data protection officer: <dsba@epicenter.works>

You have a right to information regarding your personal data (Article 15 GDPR), to correction (Article 16 GDPR), to deletion (Article 17 GDPR) or to limitation of processing (Article 18 GDPR), a right to object to the processing (Article 21 GDPR) and the right to data portability (Article 20 GDPR).
Please send these requests to <office@epicenter.works>.
You also have the right to complain to a supervisory authority, in Austria the Data Protection Authority (<https://www.dsb.gv.at>).

The personal identifiable information we processes is the IP address of users accessing the tool, the telephone number for individual or scheduled calls and potentially any personal information that the user chooses to share via the feedback form.
We will explain the different cases of processing below in detail:

## Accessing the Website

When the DearMEP tools is accessed, the IP address of the user is processed on our server, which is located in Europe.
The purpose of the processing of IP addresses is geolocating the user to a country and abuse prevention.
The geolocation lookup sets the default of the country selection to the location of the users internet connection.
This happens locally on our server in RAM memory and does not share your IP address to a third party.
In order to ensure the integrity and stability of the service, we retain the IP address to allow us for rate limiting access to our servers for the purpose of abuse prevention.
The rate limiting happens in the RAM memory of the server and is only retained as long as the service is operational uninterrupted.
Additionally, our server also logs the lower 16 bits of IPv4 and the lower 96 bits of IPv6 address as long as the campaign takes place or in case of abuse for the duration of any subsequent criminal proceedings.
The legal basis of this processing is our legitimate interest (Art. 6 (1) (f) GDPR) and legal obligations (Art. 6 (1) (c) GDPR).

## Using the Telephone Function

When you use our service for making phone calls, we ask for your consent to this privacy policy to allow us to process your telephone number.
We do not obtain or process information about contents of your phone calls once our system connects you to the Member of the European Parliament.
We use the Swedish provider 46Elks for handling the phone conversations and their privacy policy applies for calls and SMS (<https://46elks.com/privacy-policy>).

In exceptional cases we also store additional data required in order to prevent abuse of the service.
This may include information such as IP addresses, phone numbers and message content.
This information may be collected about non-users as well and only for the purpose of preventing abuse.

Our service only processes telephone numbers after you have given your informed consent to this privacy policy and only as long as there is a concrete purpose for processing it.
The legal basis of the processing of telephone numbers is informed consent (Art. 6 (1) (a) GDPR).

We built this system in a way that in many cases we do not even know your telephone number.

With four exceptions, but telephone numbers stored in our system are hashed (<https://en.wikipedia.org/wiki/Hash_function>) in order to limit the danger for the privacy of users in case the server is compromised.
Non-hashed telephone numbers are retained only once until they are confirmed via SMS token and as long as
1) there is an ongoing call subscription that has not been canceled,
2) when an individual call is initiated via the web interface and that call is ongoing,
3) a SMS with a feedback survey has not been sent (see below) or
4) when there is a reasonable suspicion that a number might be abusing our system.

We process telephone numbers in case individual calls are made with our system to a selected Politician or when there is an active call subscription in which the user requests that our system calls and connects them to a Politician of their country at a given weekday and time of weekday.
Call subscriptions can be canceled by the user at any time via the web interface or directly in the subscribed phone call with a press of a button.

The first step of processing telephone numbers is to send an SMS verification token to confirm that the telephone number entered into our system is under the users control.
SMS verification tokens that have not yet been used are deleted after a maximum of one hour.
We have limited the number of attempts a telephone number can request a confirmation token and therefore we retain numbers that have not been confirmed in a hashed format, together with the number of attempts they requested a token.
We store this information as long as the campaign takes place or in case of abuse, for the duration of any subsequent criminal proceedings, so as to prevent spamming of third-party telephone numbers with confirmation SMS.

A confirmed telephone number will create a web token in a cookie to authenticate the web browser session with which the user interacts with our service.
The telephone number is stored in the cookie which is sent to the browser in an encrypted way, in order to make the decryption of the real telephone number only possible by the server.
The authentication information is stored as a session cookie and will be deleted as soon as the browser session ends.

For the purpose of cost controlling and debugging we retain anonymised statistical information about the time, duration, destination and truncated telephone number of the user.
We might share this anonymised statistical information with the campaigns that implement this particular iteration of DearMEP for the CSAR dossier, so they can assess the impact of the tool on the political level.

In case of suspected abuse, we might add the hashed version of a telephone number to a catching circuit in our system.
In this case that phone number is retained non-hashed once it is used in our system again.
The phone number will only be processed as long as the campaign takes place or in case of abuse, for the duration of any subsequent criminal proceedings (Art. 6 (1) (c), (f) GDPR).

## Call Feedback

Once a call that lasted above a certain duration is concluded, a user will be asked to provide us feedback with a short survey that is associated with that particular call.
We may request that feedback directly in the browser and/or via an SMS text message with a unique link.
We ask if the user believes to have successfully convinced the politician, if there was a technical problem and optional additional feedback.
This information is complemented with the politician they have called, the country of the user, the hashed telephone number and the first digits of their telephone number, which only reveal their country code and provider, but not them as a subscriber. We retain the hashed telephone number so we can correlate answers back to the same user.

Calling Feedback is kept intentionally pseudonymous to allow the sharing of this information with campaigns that also implement this iteration of DearMEP without revealing any personal information of users.

In the interface of the feedback tool, the user is informed that if they wish to be contacted by us, they have to provide contact information in the additional feedback text box.
If the user provides personal information like e-mail addresses or a telephone number in that feedback text box, we rely on their informed consent as legal basis for that processing (Art. 6 (1) (a) GDPR).

## Transfer to third parties

Generally, we do not share your information to third parties without your explicit consent.
When using the call functionality, we have to share your telephone number with our telephone provider 46Elks (see above).
When this iteration of DearMEP for the CSAR legislation is implemented by campaigns that work on this legislation, we will generally provide them access to the pseudonomised call feedback (that can contain personal information that you enter into the “additional feedback” textbox) and anonymised statistical information about the use of this tool.
You can find information about the campaigns that implement this iteration of DearMEP at <https://dearmep.eu/showcase/chatcontrol/>.
