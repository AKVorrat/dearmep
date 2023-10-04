import { Component, Input } from '@angular/core';
import { CallingStep } from '../model/calling-step.enum';
import { CallingStateManagerService } from '../services/calling/calling-state-manager.service';

@Component({
  selector: 'dmep-calling',
  templateUrl: './calling.component.html',
  styleUrls: ['./calling.component.scss']
})
export class CallingComponent {
  public readonly StepHome = CallingStep.Home
  public readonly StepHomeAuthenticated = CallingStep.HomeAuthenticated
  public readonly StepVerify = CallingStep.Verify
  public readonly StepSetup = CallingStep.Setup
  public readonly StepFeedback = CallingStep.Feedback
  public readonly StepUpdateCallSchedule = CallingStep.UpdateCallSchedule

  public readonly step$

  @Input()
  public disableScheduling = false

  constructor(
    private readonly callingStateManager: CallingStateManagerService,
  ) {
    this.step$ = callingStateManager.getStep$()
  }
}
