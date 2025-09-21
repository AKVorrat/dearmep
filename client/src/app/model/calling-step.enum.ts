// SPDX-FileCopyrightText: © 2023 Tobias Mühlberger
//
// SPDX-License-Identifier: AGPL-3.0-or-later

export enum CallingStep {
  Home = 'home',
  HomeShowTalkingPoints = 'home-show-talking-points',
  HomeAuthenticated = 'home-unauthenticated',
  Verify = 'verify',
  Setup = 'call-starting',
  Feedback = 'call-feedback',
  UpdateCallSchedule = 'update-call-schedule',
}
