// SPDX-FileCopyrightText: © 2023 Tobias Mühlberger
//
// SPDX-License-Identifier: AGPL-3.0-or-later

import { Component, Input, inject } from '@angular/core';
import { CallingStep } from '../model/calling-step.enum';
import { RoutingStateManagerService } from '../services/routing/routing-state-manager.service';
import { AsyncPipe } from '@angular/common';
import { UpdateCallScheduleComponent } from './steps/update-call-schedule/update-call-schedule.component';
import { FeedbackStepComponent } from './steps/feedback-step/feedback-step.component';
import { SetupStepComponent } from './steps/setup-step/setup-step.component';
import { VerifyNumberComponent } from './steps/verify-number-step/verify-number.component';
import { HomeStepComponent } from './steps/home-step/home-step.component';

@Component({
  selector: 'dmep-calling',
  templateUrl: './calling.component.html',
  styleUrls: ['./calling.component.scss'],
  imports: [
    HomeStepComponent,
    VerifyNumberComponent,
    SetupStepComponent,
    FeedbackStepComponent,
    UpdateCallScheduleComponent,
    AsyncPipe,
  ],
})
export class CallingComponent {
  public readonly StepHome = CallingStep.Home;
  public readonly HomeShowTalkingPoints = CallingStep.HomeShowTalkingPoints;
  public readonly StepVerify = CallingStep.Verify;
  public readonly StepSetup = CallingStep.Setup;
  public readonly StepFeedback = CallingStep.Feedback;
  public readonly StepUpdateCallSchedule = CallingStep.UpdateCallSchedule;

  public readonly step$;

  @Input()
  public disableScheduling = false;

  constructor() {
    const routingStateManager = inject(RoutingStateManagerService);

    this.step$ = routingStateManager.getStep$();
  }
}
