import { Component, Input, OnChanges, OnInit, SimpleChanges, ViewEncapsulation } from '@angular/core';
import { map, Observable } from 'rxjs';
import { BaseUrlService } from './common/services/base-url.service';
import { CallingStep } from './model/calling-step.enum';
import { CallingStateManagerService } from './services/calling/calling-state-manager.service';
import { UrlUtil } from './common/util/url.util';
import { L10nService } from './services/l10n/l10n.service';

@Component({
  selector: 'dmep-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.scss'],
  encapsulation: ViewEncapsulation.ShadowDom,
})
export class AppComponent implements OnInit, OnChanges {
  public styleUrl$?: Observable<string>
  public flagsStyleUrl$?: Observable<string>
  public shouldDisplayTalkingPoints$?: Observable<boolean>
  public shouldDisplayTitle$?: Observable<boolean>
  public shouldDisplayMEP$?: Observable<boolean>

  /**
   * 'hostUrl' defines the url of the DearMEP-Backend.
   * This option is required.
   * Only absolute urls are allowed.
   */
  // eslint-disable-next-line @angular-eslint/no-input-rename
  @Input("host")
  public hostUrl?: string

  /**
   * 'assetsUrl' defines the location of all static assets such as stylesheets, fonts, ... .
   * Both absolute and relative values are allowed.
   * Relative urls are interpretet in relation to the 'hostUrl'
   * The default value is './static' ('{hostUlr}/static')
   */
  // eslint-disable-next-line @angular-eslint/no-input-rename
  @Input("assets")
  public assetsUrl = "./static"

  /**
   * 'apiUrl' defines the url of the DearMEP-API.
   * Both absolute and relative values are allowed.
   * Relative urls are interpretet in relation to the 'hostUrl'
   * The default is 'hostUrl'
   * It is not required to add the prefix '/api/v1' here since that is already built into the API-Client.
   */
  // eslint-disable-next-line @angular-eslint/no-input-rename
  @Input("api")
  public apiUrl = "./"

  /**
   * This parameter hides the call-scheduling functionality. By default scheduling is enabled.
   *
   * NOTE: Sceduling is currently disabled by default as the backend does not yet support the functionality.
   *
   * It can be applied in the HTML code by simply specifying the attribute-name:
   *
   *  <dear-mep disable-scheduling></dear-mep>
   *
   * If the attribute is present, the value of this property is '' otherwise it is undefined.
   * The getter 'disableScheduling' converts this value into a boolean accordinly.
   */
  @Input()
  public 'disable-scheduling': '' | undefined = '' // NOTE: This default will be changed to false as soon as scheduling is implemented in the backend.

  public get disableScheduling(): boolean {
    return this['disable-scheduling'] !== undefined
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
  public 'disable-calling': '' | undefined = undefined

  public get disableCalling(): boolean {
    return this['disable-calling'] !== undefined
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
  @Input("default-country")
  public defaultCountry?: string

  constructor(
    private readonly baseUrlService: BaseUrlService,
    private readonly callingStateManagerService: CallingStateManagerService,
    private readonly l10nService: L10nService,
  ) { }

  public ngOnInit() {
    if (!this.hostUrl) {
      console.error(`DearMEP: Missing required attirbute 'host'. The attribute describes the URL of the DearMEP-Backend. Without the Attribute the DearMEP-Client cannot connect to the backend. Example: <dear-mep host="https://dearmep.example.org"></dear-mep>`)
    } else if (!UrlUtil.isAbsolute(this.hostUrl)) {
      console.error(`DearMEP: Invalid attirbute 'host'. Only absolute URLs are allowed for this option.`)
    }

    this.styleUrl$ = this.baseUrlService.toAbsoluteAssetUrl$("./dear-mep-inner.css")
    this.flagsStyleUrl$ = this.baseUrlService.toAbsoluteAssetUrl$("./flags.css")

    this.shouldDisplayTalkingPoints$ = this.callingStateManagerService.getStep$().pipe(
      map(step => step !== CallingStep.Home && step !== CallingStep.HomeAuthenticated)
    );
    this.shouldDisplayTitle$ = this.callingStateManagerService.getStep$().pipe(
      map(step => step === CallingStep.Home || step === CallingStep.HomeAuthenticated || step == CallingStep.UpdateCallSchedule)
    );
    this.shouldDisplayMEP$ = this.callingStateManagerService.getStep$().pipe(
      map(step => step !== CallingStep.UpdateCallSchedule)
    )

    this.l10nService.setDefaultCountry(this.defaultCountry?.toUpperCase())
  }

  public ngOnChanges(changes: SimpleChanges): void {
    if (changes["hostUrl"] || changes["assetsUrl"]) {
      const assetsUrl = UrlUtil.toAbsolute(
        this.assetsUrl,
        this.hostUrl
      )
      this.baseUrlService.setAssetsUrl(assetsUrl)
    }
    if (changes["hostUrl"] || changes["apiUrl"]) {
      const apiUrl = UrlUtil.toAbsolute(
        this.apiUrl,
        this.hostUrl
      )
      this.baseUrlService.setAPIUrl(apiUrl)
    }
    if (changes["defaultCountry"]) {
      this.l10nService.setDefaultCountry(this.defaultCountry?.toUpperCase())
    }
  }
}
