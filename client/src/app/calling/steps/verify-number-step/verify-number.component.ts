import { Component, OnDestroy, OnInit } from '@angular/core';
import { FormControl, ValidationErrors, ValidatorFn, Validators } from '@angular/forms';
import { CallingStateManagerService } from 'src/app/services/calling/calling-state-manager.service';
import { VerificationStep } from './verification-step.enum';
import { PhoneNumber } from 'src/app/model/phone-number.model';
import { TranslocoService } from '@ngneat/transloco';
import { BaseUrlService } from 'src/app/common/services/base-url.service';
import { ApiService } from 'src/app/api/services';
import { L10nService } from 'src/app/services/l10n/l10n.service';
import { Subject } from 'rxjs/internal/Subject';
import { takeUntil } from 'rxjs';
import { HttpValidationError, PhoneNumberNotAllowedResponse, PhoneNumberVerificationResponse, SmsCodeVerificationFailedResponse } from 'src/app/api/models';
import { HttpErrorResponse } from '@angular/common/http';

@Component({
  selector: 'dmep-verify-number',
  templateUrl: './verify-number.component.html',
  styleUrls: ['./verify-number.component.scss']
})
export class VerifyNumberComponent implements OnInit, OnDestroy {
  private destroyed$ = new Subject<void>()

  private currentLanguage?: string

  public readonly StepEnterNumber = VerificationStep.EnterNumber
  public readonly StepEnterCode = VerificationStep.EnterCode
  public readonly StepSuccess = VerificationStep.Success

  public step = this.StepEnterNumber

  constructor(
    private readonly callingStateManager: CallingStateManagerService,
    private readonly translocoService: TranslocoService,
    private readonly baseUrlService: BaseUrlService,
    private readonly apiService: ApiService,
    private readonly l10nService: L10nService,
  ) {
  }

  public ngOnInit(): void {
    this.l10nService.getLanguage$().pipe(
      takeUntil(this.destroyed$)
    ).subscribe({
      next: (l) => this.currentLanguage = l
    })
  }

  public ngOnDestroy(): void {
    this.destroyed$.next()
    this.destroyed$.complete()
  }

  public numberFormControl = new FormControl<PhoneNumber>({ callingCode: "+43", number: "" }, {
    validators: this.numberValidator,
    updateOn: 'change',
  })
  public acceptPolicy = false

  public codeFormControl = new FormControl<string | null>(null, {
    validators: [ Validators.required ],
    updateOn: 'change',
  })

  public validatedPhoneNumber?: string;

  public onEditNumberClick() {
    this.step = VerificationStep.EnterNumber
  }

  public onSendCodeClick() {
    if (!this.acceptPolicy || !this.currentLanguage) {
      return
    }

    this.apiService.requestNumberVerification({
      body: {
        phone_number: this.phoneNumberToString(this.numberFormControl.value),
        language: this.currentLanguage,
        accepted_dpp: this.acceptPolicy,
      }
    }).subscribe({
      next: (response: PhoneNumberVerificationResponse) => {
        this.numberFormControl.setErrors(null)
        this.validatedPhoneNumber = response.phone_number;
        this.step = VerificationStep.EnterCode
      },
      error: (err: HttpErrorResponse | unknown) => {
        if (err instanceof HttpErrorResponse && err.status === 422) {
          console.log("invalid number")
          this.numberFormControl.setErrors({ numberValidationError: true })
        } else if (err instanceof HttpErrorResponse && err.error.error === 'NUMBER_NOT_ALLOWED') {
          console.log("number not allowed")
          this.numberFormControl.setErrors({ numberNotAllowed: true })
        } else {
          console.log("other error")
          this.numberFormControl.setErrors({ numberValidationError: true })
        }
      }
    })
  }

  public onVerifyCodeClick() {
    if (!this.codeFormControl.value || !this.validatedPhoneNumber) {
      return
    }

    this.apiService.verifyNumber({
      body: {
        code: this.codeFormControl.value,
        phone_number: this.validatedPhoneNumber,
      }
    }).subscribe({
      next: (response) => {
        // TODO: store jwt
        this.step = VerificationStep.Success
      },
      error: (err: HttpErrorResponse | unknown) => {
        if (err instanceof HttpErrorResponse && (err.status === 400 || err.status === 422)) {
          this.codeFormControl.setErrors({ invalidCode: true })
        } else {
          console.error(err)
        }
      }
    })
  }

  public onCallNowClick() {


    this.callingStateManager.setUpCall()
  }

  public onCallLaterClick() {
    this.callingStateManager.goToSchedule()
  }

  public getPolicyLinkHtml(): string {
    const policyUrlKey = 'verification.enterNumber.policyLinkUrl'
    const policyUrl = this.translocoService.translate(policyUrlKey)
    let linkText = this.translocoService.translate('verification.enterNumber.policyLinkText')

    if (policyUrl === policyUrlKey) {
      console.error("Missing privacy policy url!")
    }
    if (!linkText) {
      linkText = policyUrl
    }

    let absPolicyUrl = policyUrl
    try {
      absPolicyUrl = this.baseUrlService.toAbsoluteAPIUrl(policyUrl)
    } catch (err) {
      console.error("failed to convert url to absolute", err)
    }

    return `<a href="${ absPolicyUrl }" target="_blank">${ linkText }</a>`
  }

  private phoneNumberToString(number: PhoneNumber | null): string {
    if (!number  || !number.callingCode || !number.number) {
      return ''
    }
    return `${number.callingCode} ${number.number}`
  }
}
