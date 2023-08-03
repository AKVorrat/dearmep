import { Component, Input, OnChanges, OnInit, SimpleChanges, ViewEncapsulation } from '@angular/core';
import { map, Observable } from 'rxjs';
import { BaseUrlService } from './common/services/base-url.service';
import { CallingStep } from './model/calling-step.enum';
import { CallingStateManagerService } from './services/calling/calling-state-manager.service';
import { UrlUtil } from './common/util/url.util';

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

  // eslint-disable-next-line @angular-eslint/no-input-rename
  @Input("disable-calling")
  public disableCalling = false

  constructor(
    private readonly assetsBaseUrlService: BaseUrlService,
    private readonly callingStateManagerService: CallingStateManagerService,
  ) {}

  public ngOnInit() {
    if (!this.hostUrl) {
      console.error(`DearMEP: Missing required attirbute 'host'. The attribute describes the URL of the DearMEP-Backend. Without the Attribute the DearMEP-Client cannot connect to the backend. Example: <dear-mep host="https://dearmep.example.org"></dear-mep>`)
    } else if (!UrlUtil.isAbsolute(this.hostUrl)) {
      console.error(`DearMEP: Invalid attirbute 'host'. Only absolute URLs are allowed for this option.`)
    }

    this.styleUrl$ = this.assetsBaseUrlService.toAbsoluteUrl$("./styles.css")
    this.flagsStyleUrl$ = this.assetsBaseUrlService.toAbsoluteUrl$("./flags.css")
    this.shouldDisplayTalkingPoints$ = this.callingStateManagerService.getStep$().pipe(
      map(step => step !== CallingStep.Home && step !== CallingStep.HomeAuthenticated)
    );
    this.shouldDisplayTitle$ = this.callingStateManagerService.getStep$().pipe(
      map(step => step === CallingStep.Home || step === CallingStep.HomeAuthenticated || step == CallingStep.UpdateCallSchedule)
    );
    this.shouldDisplayMEP$ = this.callingStateManagerService.getStep$().pipe(
      map(step => step !== CallingStep.UpdateCallSchedule)
    )
  }

  public ngOnChanges(changes: SimpleChanges): void {
    if ((changes["hostUrl"] && this.hostUrl) || 
        (changes["assetsUrl"] && this.assetsUrl)) {
      const assetsUrl = this.getAssetsUrl()
      this.assetsBaseUrlService.setBaseUrl(assetsUrl)
    }
  }

  private getAssetsUrl(): string {
    return UrlUtil.toAbsolute(
      this.assetsUrl,
      this.hostUrl
    )
  }
}