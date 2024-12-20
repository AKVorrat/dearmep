<!--
SPDX-FileCopyrightText: © 2022 Tim Weber
SPDX-FileCopyrightText: © 2023 Thomas Lohninger

SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Glossary

## Campaign

A given website embedding the frontend snippet.

DearMEP was created with the European Parliament and several national initiatives working towards the same goal, and with the same dataset, but each having their own website, in mind.

“Campaign” can also be used to refer to the endeavour to influence political decision-making as a whole, e.g. “the campaign against X”.

## Conversion

The process of converting someone who browses the Campaign website to an actual User in the system, i.e. to someone who uses the application to contact Destinations.

## Instance

When the DearMEP Tool is applied for a particular campaign it needs to be centrally hosted and configured. Texts and audio files have to be adapted for that issue. MEPs of the current legislative term have to be uploaded with their sway-ability value. We call such a running version of DearMEP an Instance.

## Campaign
Every instance can be embedded in multiple campaign websites, which might do further configuration for their particular use case. We call such an embed of an instance a Campaign.

## Destination

One of the persons that the application is configured to contact in the current campaign, e.g. a member of (the European) parliament.

Other terms for these persons and why we have decided against them:

* **Callee** is focused on phone calls only, but there are other ways to contact a Destination. Also, Users are also called by the application, making the term “callee” ambiguous.
* **Member of Parliament** are the Destinations the application was initially designed to contact, but what if an initiative wants to target another group of people?

## Direct Call

A call to a Destination, initiated by a User using their own phone.
The application is not involved in this call at all, other than possibly providing the User with one or more Destination suggestions.

## Instance

One particular server-side deployment of the application.
Each Instance has its own configuration, database, and Destinations.

One Instance can serve multiple Campaigns.

## Instant Call

A call to a Destination, requested by a User to be established instantaneously.
The call will be created via the application, first calling the User, then connecting them to the Destination.

## Priority

A Destination that has been deemed by the application to be a good campaign target at this point in time.
The “value” of Destinations can change over time, causing different Destinations to be a Priority during the course of the campaign.

## Rate Limit

A technique being used to ensure that a certain action (e.g. requesting an API endpoint, or sending a text message) cannot be performed more than a certain number of times in a given timeframe.

Rate Limits can use additional parameters:
Instead of saying “don’t send more than 50 text messages per minute”, we can instead define “don’t send more than 5 text messages per minute requested by a single IP address”, or combine both approaches.

## Schedule

A set of time spans which the User has designated as being a good time for establishing a Scheduled Call.

## Scheduled Call

A call to a Destination, initiated by an automated process of the application that will pair User schedules to Destinations.
The call will be created via the application, first calling the User to confirm they’re available, then connecting them to a Priority.

## Session Token

A [JSON Web Token](https://en.wikipedia.org/wiki/JSON_Web_Token), stored in a short-lived cookie in the User’s browser, verifying that they own a certain phone number.

## User

A user of the software, e.g. a citizen or activist.

## Verification Code

A six-digit one-time code, sent via SMS text message, to the phone number the User claims to be theirs.
It can be converted into a Session Token by calling the respective API endpoint.
