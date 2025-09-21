// SPDX-FileCopyrightText: © 2024 Tobias Mühlberger
//
// SPDX-License-Identifier: AGPL-3.0-or-later

import { Component, EventEmitter, Input, Output } from '@angular/core';
import { MatIcon } from '@angular/material/icon';
import { MatError } from '@angular/material/form-field';
import { MatButton } from '@angular/material/button';
import { TranslocoModule } from '@ngneat/transloco';
import { CdkConnectedOverlay, CdkOverlayOrigin } from '@angular/cdk/overlay';

@Component({
  selector: 'dmep-calling-buttons',
  templateUrl: './calling-buttons.component.html',
  styleUrls: ['./calling-buttons.component.scss'],
  imports: [
    CdkConnectedOverlay,
    TranslocoModule,
    CdkOverlayOrigin,
    MatButton,
    MatError,
    MatIcon,
  ],
})
export class CallingButtonsComponent {
  @Input()
  public disableScheduling = false;

  @Input()
  public isOfficeHours = true;

  @Input()
  public officeHoursTimezone = '';

  @Input()
  public officeHoursText: string[] = [];

  @Input()
  public disabled = false;

  @Input()
  public allowShowTalkingPoints = false;

  @Output()
  public callNowClick = new EventEmitter();

  @Output()
  public callLaterClick = new EventEmitter();

  @Output()
  public showTalkinPointsClick = new EventEmitter();

  public officeHoursPopoverOpen = false;

  public onCallLaterClick() {
    if (!this.disabled) {
      this.callLaterClick.emit();
    }
  }

  public onCallNowClick() {
    if (this.isOfficeHours && !this.disabled) {
      this.callNowClick.emit();
    }
  }

  public onCallNowContainerClick() {
    if (!this.isOfficeHours) {
      this.officeHoursPopoverOpen = true;
    }
  }

  public onTalkingPointsClick() {
    if (this.allowShowTalkingPoints) {
      this.showTalkinPointsClick.emit();
    }
  }
}
