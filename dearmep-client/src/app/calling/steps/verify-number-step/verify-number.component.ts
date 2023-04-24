import { Component } from '@angular/core';
import { FormControl, ValidationErrors, ValidatorFn } from '@angular/forms';
import { CallingStateManagerService } from 'src/app/services/calling/calling-state-manager.service';
import { VerificationStep } from './verification-step.enum';
import { PhoneNumber } from 'src/app/model/phone-number.model';

@Component({
  selector: 'dmep-verify-number',
  templateUrl: './verify-number.component.html',
  styleUrls: ['./verify-number.component.scss']
})
export class VerifyNumberComponent {
  private readonly numberValidator: ValidatorFn = (control): ValidationErrors | null => {
    const number: PhoneNumber | null | undefined = control.value
    if (number && number.callingCode && number.number) {
      return null
    }
    return { numberError: "invalid-number" }
  }

  private readonly codeValidator: ValidatorFn = (control): ValidationErrors | null => {
    if (control.value?.length > 0) {
      return null
    }
    return { numberError: "invalid-code" }
  }

  public readonly StepEnterNumber = VerificationStep.EnterNumber
  public readonly StepEnterCode = VerificationStep.EnterCode
  public readonly StepSuccess = VerificationStep.Success

  public step = this.StepEnterNumber

  constructor(
    private readonly callingStateManager: CallingStateManagerService,
  ) { 
  }

  public numberFormControl = new FormControl<PhoneNumber>({ callingCode: "+43", number: "" }, {
    validators: this.numberValidator,
    updateOn: 'change',
  })
  public acceptPolicy = false

  public codeFormControl = new FormControl<string | null>(null, {
    validators: this.codeValidator,
    updateOn: 'change',
  })

  public onEditNumberClick() {
    this.step = VerificationStep.EnterNumber
  }

  public onSendCodeClick() {
    this.step = VerificationStep.EnterCode
  }

  public onVerifyCodeClick() {
    this.step = VerificationStep.Success
  }

  public onCallNowClick() {
    this.callingStateManager.setUpCall()
  }

  public onCallLaterClick() {
    this.callingStateManager.goToSchedule()
  }

  public getSelectedNumber(): string | undefined {
    const number = this.numberFormControl.value
    return number ? `${number.callingCode} ${number.number}` : undefined
  }
}
