import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { SelectMEPComponent } from './select-mep/select-mep.component';
import { TitleComponent } from './title/title.component';
import { TranslocoModule } from '@ngneat/transloco';
import { MEPDetailComponent } from './mep-detail/mep-detail.component';
import { AppCommonModule } from '../common/app-common.module';
import { LanguageSwitchComponent } from './language-switch/language-switch.component';
import { TalkingPointsComponent } from './talking-points/talking-points.component';

@NgModule({
  declarations: [
    SelectMEPComponent,
    TitleComponent,
    MEPDetailComponent,
    LanguageSwitchComponent,
    TalkingPointsComponent
  ],
  imports: [
    AppCommonModule,
    CommonModule,
    TranslocoModule,
  ],
  exports: [
    SelectMEPComponent,
    TitleComponent,
    MEPDetailComponent,
    LanguageSwitchComponent,
  ]
})
export class ComponentsModule { }