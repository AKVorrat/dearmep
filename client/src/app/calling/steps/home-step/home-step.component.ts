import { Component, Input } from '@angular/core';
import { TranslocoService } from '@ngneat/transloco';
import { filter } from 'rxjs';
import { CallingStateManagerService } from 'src/app/services/calling/calling-state-manager.service';

@Component({
  selector: 'dmep-home-step',
  templateUrl: './home-step.component.html',
  styleUrls: ['./home-step.component.scss']
})
export class HomeStepComponent {
  public descriptions$

  @Input()
  public disableScheduling = false

  constructor(
    private readonly callingStateManager: CallingStateManagerService,
    private readonly translocoService: TranslocoService,
  ) {
    this.descriptions$ = this.translocoService.selectTranslate('call.home.descriptions').pipe(
      filter(d => Array.isArray(d))
    )
  }

  public onCallNowClick() {
    this.callingStateManager.goToVerify()
  }

  public onCallLaterClick() {
    this.callingStateManager.goToSchedule()
  }
}
