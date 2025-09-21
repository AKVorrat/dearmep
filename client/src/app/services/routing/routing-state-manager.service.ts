// SPDX-FileCopyrightText: © 2023 Tobias Mühlberger
//
// SPDX-License-Identifier: AGPL-3.0-or-later

import { Injectable, inject } from '@angular/core';
import { BehaviorSubject } from 'rxjs';
import { CallingStep } from 'src/app/model/calling-step.enum';
import { AuthenticationService } from '../authentication/authentication.service';

@Injectable({
  providedIn: 'root',
})
export class RoutingStateManagerService {
  private readonly authService = inject(AuthenticationService);

  private readonly step$ = new BehaviorSubject<CallingStep>(CallingStep.Home);

  public getStep$() {
    return this.step$.asObservable();
  }

  public callNow() {
    if (!this.authService.isAuthenticated()) {
      this.goToVerify();
    } else {
      this.step$.next(CallingStep.Setup);
    }
  }

  public scheduleCall() {
    if (!this.authService.isAuthenticated()) {
      this.goToVerify();
    } else {
      this.step$.next(CallingStep.UpdateCallSchedule);
    }
  }

  public goToFeedback() {
    this.step$.next(CallingStep.Feedback);
  }

  public returnHome() {
    this.step$.next(CallingStep.Home);
  }

  public showTalkingPoints() {
    if (this.step$.value === CallingStep.Home) {
      this.step$.next(CallingStep.HomeShowTalkingPoints);
      console.log('Calling step', CallingStep.HomeShowTalkingPoints);
    }
  }

  private goToVerify() {
    this.step$.next(CallingStep.Verify);
  }
}
