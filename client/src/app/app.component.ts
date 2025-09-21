// SPDX-FileCopyrightText: © 2023 Tobias Mühlberger
//
// SPDX-License-Identifier: AGPL-3.0-or-later

import {
  AfterViewInit,
  Component,
  Input,
  OnChanges,
  OnInit,
  SimpleChanges,
  ViewChild,
  ViewEncapsulation,
  inject,
} from '@angular/core';
import { delay, filter, map, Observable, timer } from 'rxjs';
import { BaseUrlService } from './common/services/base-url.service';
import { CallingStep } from './model/calling-step.enum';
import { RoutingStateManagerService } from './services/routing/routing-state-manager.service';
import { UrlUtil } from './common/util/url.util';
import { L10nService } from './services/l10n/l10n.service';
import { ConfigService } from './services/config/config.service';
import { CdkConnectedOverlay, CdkOverlayOrigin } from '@angular/cdk/overlay';
import { SafePipe } from './common/pipes/safe.pipe';
import { TranslocoModule } from '@ngneat/transloco';
import { MatIcon } from '@angular/material/icon';
import { FooterComponent } from './components/footer/footer.component';
import { CallingComponent } from './calling/calling.component';
import { LanguageSwitchComponent } from './components/language-switch/language-switch.component';
import { TalkingPointsComponent } from './components/talking-points/talking-points.component';
import { SelectMEPComponent } from './components/select-mep/select-mep.component';
import { TitleComponent } from './components/title/title.component';
import { NgClass, AsyncPipe } from '@angular/common';
import { ResponsiveDirective } from './common/directives/responsive.directive';

@Component({
  selector: 'dmep-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.scss'],
  encapsulation: ViewEncapsulation.ShadowDom,
  imports: [
    ResponsiveDirective,
    CdkOverlayOrigin,
    NgClass,
    TitleComponent,
    SelectMEPComponent,
    TalkingPointsComponent,
    LanguageSwitchComponent,
    CallingComponent,
    FooterComponent,
    CdkConnectedOverlay,
    MatIcon,
    AsyncPipe,
    TranslocoModule,
    SafePipe,
  ],
})
export class AppComponent implements OnInit, OnChanges, AfterViewInit {
  private readonly baseUrlService = inject(BaseUrlService);
  private readonly routingStateManagerService = inject(
    RoutingStateManagerService
  );
  private readonly l10nService = inject(L10nService);
  private readonly configService = inject(ConfigService);

  public styleUrl$?: Observable<string>;
  public flagsStyleUrl$?: Observable<string>;
  public shouldDisplayTalkingPoints$?: Observable<boolean>;
  public shouldDisplayTitle$?: Observable<boolean>;
  public shouldDisplayMEP$?: Observable<boolean>;
  public showMaintenanceOverlay = false;
  public maintenanceOverlayDismissable = false;

  @ViewChild('maintenanceOverlay')
  public maintenanceOverlay: CdkConnectedOverlay | undefined;

  /**
   * 'hostUrl' defines the url of the DearMEP-Backend.
   * This option is required.
   * Only absolute urls are allowed.
   */
  // eslint-disable-next-line @angular-eslint/no-input-rename
  @Input('host')
  public hostUrl?: string;

  /**
   * 'assetsUrl' defines the location of all static assets such as stylesheets, fonts, ... .
   * Both absolute and relative values are allowed.
   * Relative urls are interpreted in relation to the 'hostUrl'
   * The default value is './static' ('{hostUlr}/static')
   */
  // eslint-disable-next-line @angular-eslint/no-input-rename
  @Input('assets')
  public assetsUrl = './static';

  /**
   * 'apiUrl' defines the url of the DearMEP-API.
   * Both absolute and relative values are allowed.
   * Relative urls are interpreted in relation to the 'hostUrl'
   * The default is 'hostUrl'
   * It is not required to add the prefix '/api/v1' here since that is already built into the API-Client.
   */
  // eslint-disable-next-line @angular-eslint/no-input-rename
  @Input('api')
  public apiUrl = './';

  /**
   * This parameter hides the call-scheduling functionality. By default scheduling is enabled.
   *
   * It can be applied in the HTML code by simply specifying the attribute-name:
   *
   *  <dear-mep disable-scheduling></dear-mep>
   *
   * If the attribute is present, the value of this property is '' otherwise it is undefined.
   * The getter 'disableScheduling' converts this value into a boolean accordinly.
   */
  @Input()
  public 'disable-scheduling': '' | undefined = undefined;

  public get disableScheduling(): boolean {
    return this.convertBooleanAttribute(this['disable-scheduling']);
  }

  /**
   * This parameter hides the calling functionality. By default calling is enabled.
   *
   * It can be applied in the HTML code by simply specifying the attribute-name:
   *
   *  <dear-mep disable-calling></dear-mep>
   *
   * If the attribute is present, the value of this property is '' otherwise it is undefined.
   * The getter 'disableCalling' converts this value into a boolean accordinly.
   */
  @Input()
  public 'disable-calling': '' | undefined = undefined;

  public get disableCalling(): boolean {
    return this.convertBooleanAttribute(this['disable-calling']);
  }

  /**
   * If the country the user is in cannot be detected by the backend or
   * the detected country is not among the available countries, this
   * country is used by default.
   * This could for example be the case when the user is traveling abroad
   * or uses TOR or a VPN service.
   * If this value is not configured a country is choosen at at random
   * from the list of available countries.
   * The value must be a two didgit country-code (e.g. "AT").
   * Country-Codes can be found here: https://en.wikipedia.org/wiki/List_of_ISO_3166_country_codes
   */
  // eslint-disable-next-line @angular-eslint/no-input-rename
  @Input('default-country')
  public defaultCountry?: string;

  public ngOnInit() {
    if (!this.hostUrl) {
      console.error(
        `DearMEP: Missing required attirbute 'host'. The attribute describes the URL of the DearMEP-Backend. Without the Attribute the DearMEP-Client cannot connect to the backend. Example: <dear-mep host="https://dearmep.example.org"></dear-mep>`
      );
    } else if (!UrlUtil.isAbsolute(this.hostUrl)) {
      console.error(
        `DearMEP: Invalid attirbute 'host'. Only absolute URLs are allowed for this option.`
      );
    }

    this.styleUrl$ = this.baseUrlService.toAbsoluteAssetUrl$(
      './dear-mep-inner.css'
    );
    this.flagsStyleUrl$ =
      this.baseUrlService.toAbsoluteAssetUrl$('./flags.css');

    this.shouldDisplayTalkingPoints$ = this.routingStateManagerService
      .getStep$()
      .pipe(
        map(
          step =>
            step !== CallingStep.Home && step !== CallingStep.HomeAuthenticated
        )
      );
    this.shouldDisplayTitle$ = this.routingStateManagerService
      .getStep$()
      .pipe(
        map(
          step =>
            step === CallingStep.Home ||
            step === CallingStep.HomeAuthenticated ||
            step === CallingStep.UpdateCallSchedule
        )
      );
    this.shouldDisplayMEP$ = this.routingStateManagerService
      .getStep$()
      .pipe(map(step => step !== CallingStep.UpdateCallSchedule));

    this.l10nService.setDefaultCountry(this.defaultCountry?.toUpperCase());
  }

  public ngAfterViewInit() {
    this.configService
      .getConfig$()
      .pipe(delay(50))
      .subscribe({
        next: config => {
          this.showMaintenanceOverlay = !!config.features.maintenance?.active;
          this.maintenanceOverlayDismissable =
            !!config.features.maintenance?.message?.dismissable;
        },
      });

    // make sure the overlay is positioned correctly after the content has been rendered
    timer(500)
      .pipe(filter(() => this.showMaintenanceOverlay))
      .subscribe({
        next: () => this.maintenanceOverlay?.overlayRef?.updatePosition(),
      });
  }

  public ngOnChanges(changes: SimpleChanges): void {
    if (changes['hostUrl'] || changes['assetsUrl']) {
      const assetsUrl = UrlUtil.toAbsolute(this.assetsUrl, this.hostUrl);
      this.baseUrlService.setAssetsUrl(assetsUrl);
    }
    if (changes['hostUrl'] || changes['apiUrl']) {
      const apiUrl = UrlUtil.toAbsolute(this.apiUrl, this.hostUrl);
      this.baseUrlService.setAPIUrl(apiUrl);
    }
    if (changes['defaultCountry']) {
      this.l10nService.setDefaultCountry(this.defaultCountry?.toUpperCase());
    }
  }

  public onMaintenanceOverlayDismissClick() {
    if (this.maintenanceOverlayDismissable) {
      this.showMaintenanceOverlay = false;
    }
  }

  private convertBooleanAttribute(
    attrValue: string | null | undefined
  ): boolean {
    return !(
      attrValue === null ||
      attrValue === undefined ||
      attrValue.toLowerCase() === 'false'
    );
  }
}
