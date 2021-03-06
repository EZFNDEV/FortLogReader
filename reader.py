import os
import time
import json
import datetime

from threading import Thread

logs_dir = r'logs'
logs_read = 0
file_count = 0
versions = {}
blacklist = json.loads(open('blacklist.json').read())

CurrentPackets = {'InPackets': [], 'OutPackets': []}
RPC_Functions = json.loads(open('RPC_Functions.json').read())

# TODO: Parse the XMPP, maybe there is a module to do it
def parse_xmpp(message: str):
    return {}

def parse(filepath: str):
    global logs_read, file_count, CurrentPackets, RPC_Functions

    Build = None
    CurrentSessionID = ''

    try:
        lines = open(f'{logs_dir}/{filepath}').readlines()
    except:
        try:
            lines = open(f'{logs_dir}/{filepath}', 'rb').read().decode('utf8').split('\r\n')
        except:
            print(f'{filepath} can not be read!')
            logs_read += 1
            file_count -= 1
            return
        # print(f'{filepath} might not be read correctly!')

    if not 'Log file open' in lines[0]:
        logs_read += 1
        file_count -= 1
        return

    try:
        # CreatedAt = datetime.datetime.strptime(lines[0].split('Log file open, ')[1].strip(),'%m/%d/%y %H:%M:%S')
        CreatedAt = lines[0].split('Log file open, ')[1].strip()
    except Exception as e:
        CreatedAt = 'Failed to parse'

    for idx, line in enumerate(lines[1:]):
        try:
            line = line.strip()

            if any(b in line for b in blacklist):
                continue

            # Detect and remove the timestap
            ActionNumber = None
            if line.startswith('['):
                try:
                    time = datetime.datetime.strptime(line.split('[')[1].split(']')[0],'%Y.%m.%d-%H.%M.%S:%f')
                except:
                    continue
                # Read the "Command Number" called __LINE__ in UE4
                ActionNumber = int(line.split('[')[2].split(']')[0].strip())
                line = ']'.join(line.split(']')[2:])

                if not lines[idx + 1].startswith('['):
                    # TODO: Skip the next line in the for loop and parse this too, probably a response with next lines
                    print(f'Failed to parse next line! {line}')

            if ActionNumber != None and not ActionNumber in versions[Build]["Actions"]:
                versions[Build]["Actions"][ActionNumber] = {}

            # Check if the line has a response
            if ' response=' in line and 'url=' in line and Build:
                try:
                    url = line.split('url=')[1].split(' ')[0]
                    if 'code=' in line:
                        response_code = line.split('code=')[1].split(' ')[0]
                    else:
                        response_code = 'Failed to parse'
                    response = line.split('response=')[1].strip()
                    try:
                        response = json.loads(response)
                    except:
                        pass
                    
                    if not 'HTTPRequests' in versions[Build]["Actions"][ActionNumber]:
                        versions[Build]["Actions"][ActionNumber]['HTTPRequests'] = []

                    versions[Build]["Actions"][ActionNumber]['HTTPRequests'].append({
                        'url': url,
                        'response_code': response_code,
                        'response': response
                    })
                except Exception as e:
                    print(f'Failed to parse this line: {line}\nError: {e}')
                continue
                # Skip next steps, we are done with this line

            # Get the "CategoryName"
            if line.split(':')[0].startswith('[20'):
                CategoryName = line.split(']')[2].split(':')[0]
            else:
                CategoryName = line.split(':')[0]

            # This does not always exist
            try:
                LogSubType = line.split(':')[1].strip()
                Result = ':'.join(line.split(':')[2:]).strip()
            except Exception as e:
                LogSubType = ""
                Result = ""
            
            # Get by CategoryName
            if CategoryName == 'LogInit':
                if LogSubType == 'Build':
                    Build = Result
                    versions[Build] = {'Build': Build, 'CreatedAt': CreatedAt, 'Actions': {}, 'Init': {}, 'Matches': {}}
                elif Build:
                    if LogSubType.startswith('- '):
                        continue

                    if LogSubType == 'Filtered Command Line':
                        for Command in Result.split(' -'):
                            if '=' in Command:
                                versions[Build][Command.split('=')[0]] = Command.split('=')[1]
                    elif LogSubType == 'OS':
                        versions[Build]['Init'][LogSubType] = {
                            'Platform': Result.split(' (), ')[0],
                            'CPU': Result.split(', CPU: ')[1].split(', ')[0].strip(),
                            'GPU': Result.split(', GPU: ')[1]
                        }
                    elif LogSubType == 'WinSock':
                        if 'version' in Result and 'MaxUdp' in Result and 'MaxSocks' in Result:
                            if not LogSubType in versions[Build]['Init']:
                                versions[Build]['Init'][LogSubType] = {}

                            versions[Build]['Init'][LogSubType]['version'] = Result.split('version ')[1].split(',')[0]
                            versions[Build]['Init'][LogSubType]['MaxSocks'] = Result.split(', MaxSocks=')[1].split(',')[0]
                            versions[Build]['Init'][LogSubType]['MaxUdp'] = Result.split(', MaxUdp=')[1]
                        elif Result.startswith('Socket queue.'):
                            if not LogSubType in versions[Build]['Init']:
                                versions[Build]['Init'][LogSubType] = {}
                            
                            versions[Build]['Init'][LogSubType]['Rx'] = Result.split(' Rx: ')[1].split(' Tx: ')[0]
                            versions[Build]['Init'][LogSubType]['Tx'] = Result.split(' Tx: ')[1]
                        elif Result.startswith('I am '):
                            if not LogSubType in versions[Build]['Init']:
                                versions[Build]['Init'][LogSubType] = {}
                            
                            versions[Build]['Init'][LogSubType]['IP'] = Result.split(' (')[1].split(')')[0]
                            versions[Build]['Init'][LogSubType]['PC-Name'] = Result.split('I am ')[1].split(' (')[0]
                    elif line.endswith(':'):
                        versions[Build]['Init'][LogSubType] = {}
                        current_idx = idx
                        while lines[current_idx + 1].startswith('LogInit:  - ') or 'LogInit:  - ' in lines[current_idx + 1]:
                            if n_line.startswith('['):
                                n_line = ']'.join(lines[current_idx + 1].split(']')[2:])
                            else:
                                n_line = lines[current_idx + 1]
                            if '  - ' in n_line:
                                n_line = n_line.split('  - ')[0]
                            if '  - ' in n_line:
                                n_line = n_line.split('  - ')[1]
                            if ' = ' in n_line:
                                versions[Build]['Init'][LogSubType][n_line.split(' = ')[0]] = n_line.split(' = ')[1]
                            current_idx += 1
                    else:
                        versions[Build]['Init'][LogSubType] = Result
            elif Build:
                if CategoryName == 'LogXmpp':
                    if not 'XMPP' in versions[Build]["Actions"][ActionNumber]:
                        versions[Build]["Actions"][ActionNumber]['XMPP'] = {'Messages': []}
                        
                    if 'server = ' in line:
                        versions[Build]["Actions"][ActionNumber]['XMPP']['Server'] = line.split('server = ')[1]
                    elif 'user = ' in line:
                        versions[Build]["Actions"][ActionNumber]['XMPP']['JID'] = line.split('user = ')[1]
                        versions[Build]["Actions"][ActionNumber]['XMPP']['UserID'] = line.split('user = ')[1].split(':')[0]
                        versions[Build]["Actions"][ActionNumber]['XMPP']['Platform'] = line.split('user = ')[1].split(':')[3]
                    elif LogSubType == 'VeryVerbose':
                        # Sent
                        if 'xmpp debug: RECV:' in line:
                            versions[Build]["Actions"][ActionNumber]['XMPP']['Messages'].append({
                                'Incoming': True,
                                'Outgoing': False,
                                'RawMessage': line.split('xmpp debug: RECV: ')[1]
                            })
                        # Received
                        elif 'conn debug: SENT:' in line:
                            versions[Build]["Actions"][ActionNumber]['XMPP']['Messages'].append({
                                'Incoming': False,
                                'Outgoing': True,
                                'RawMessage': line.split('conn debug: SENT: ')[1]
                            })
                        else:
                            pass
                elif CategoryName == 'PacketHandlerLog':
                    if LogSubType == 'Loaded PacketHandler component':
                        if not 'PacketHandler' in versions[Build]["Actions"][ActionNumber]:
                            versions[Build]["Actions"][ActionNumber]['PacketHandler'] = {'Components': {}}

                        component = Result.split(' ')[0]
                        if not component in versions[Build]["Actions"][ActionNumber]['PacketHandler']['Components']:
                            versions[Build]["Actions"][ActionNumber]['PacketHandler']['Components'][component] = {'Incoming': []}
                    elif LogSubType == 'FAESGCMHandlerComponent':
                        if not 'PacketHandler' in versions[Build]["Actions"][ActionNumber]:
                            versions[Build]["Actions"][ActionNumber]['PacketHandler'] = {'Components': {}}
                            
                        if not 'AESGCMHandlerComponent' in versions[Build]["Actions"][ActionNumber]['PacketHandler']['Components']:
                            versions[Build]["Actions"][ActionNumber]['PacketHandler']['Components']['AESGCMHandlerComponent'] = {'Incoming': []}
                        if line.startswith('PacketHandlerLog: FAESGCMHandlerComponent::Incoming:'):
                            versions[Build]["Actions"][ActionNumber]['PacketHandler']['Components']['AESGCMHandlerComponent']['Incoming'].append(line.split('PacketHandlerLog: FAESGCMHandlerComponent::Incoming: ')[1])
                elif CategoryName == 'LogSecurity':
                    if not 'Security' in versions[Build]["Actions"][ActionNumber]:
                        versions[Build]["Actions"][ActionNumber]['Security'] = {'Warnings': []}
                    if LogSubType == 'Warning':
                        # PacketHandler
                        # TODO: Add more / enable logging all
                        IP = line.split(':')[2].strip()
                        Port = line.split(':')[3].strip()
                        versions[Build]["Actions"][ActionNumber]['Security']['Warnings'].append({
                            'ServerAddress': IP,
                            'Port': Port,
                            'Type': line.split(':')[4].strip(),
                            'Message': (':'.join(line.split(':')[5:]))[1:]
                        })
                elif CategoryName == 'LogContentBeacon':
                    if 'RequestConnection() connectURL:' in line:
                        IP = line.split('RequestConnection() connectURL: ')[1].split(':')[0]
                        Port = line.split('RequestConnection() connectURL: ')[1].split(':')[1].split('/')[0]
                        Map = line.split(f'RequestConnection() connectURL: {IP}:{Port}')[1]
                        versions[Build]["Actions"][ActionNumber]['Beacon'] = {'ServerAddress' : IP,'Port': Port,'Map': Map, 'Errors': [], 'Warning': []}
                    elif line == 'LogContentBeacon: Contentbeacon RequestConnection() Succesfully Connected':
                        if 'Beacon' in versions[Build]["Actions"][ActionNumber]:
                            versions[Build]["Actions"][ActionNumber]['Beacon']['Connected'] = True
                    # Errors
                    elif line == 'LogContentBeacon: AContentBeaconClient OnFailure Failed to connect':
                        if not 'Beacon' in versions[Build]["Actions"][ActionNumber]:
                            versions[Build]["Actions"][ActionNumber]['Beacon'] = {'Errors': [], 'Warning': []}
                        versions[Build]["Actions"][ActionNumber]['Beacon']['Errors'].append(line)
                elif CategoryName == 'LogNet':
                    if LogSubType == 'Warning':
                        if not 'Beacon' in versions[Build]["Actions"][ActionNumber]:
                            versions[Build]["Actions"][ActionNumber]['Beacon'] = {'Errors': [], 'Warning': []}
                        versions[Build]["Actions"][ActionNumber]['Beacon']['Warning'].append(Result)
                    elif LogSubType == 'Browse':
                        try:
                            IP = line.split('LogNet: Browse: ')[1].split(':')[0]
                            Port = line.split('LogNet: Browse: ')[1].split(':')[1].split('/')[0]
                            Map = line.split(f'LogNet: Browse: {IP}:{Port}')[1]
                        except:
                            IP = ''
                            Port = ''
                            Map = line.split(f'LogNet: Browse: ')[1]
                        Query = {}
                        if '?' in Map:
                            for q in Map.split('?')[1:]:
                                if '=' in q:
                                    Query[q.split('=')[0]] = q.split('=')[1]
                                else:
                                    Query[q.split('=')[0]] = ''
                            Map = Map.split('?')[0]
                        versions[Build]["Actions"][ActionNumber]['GameServer'] = {'ServerAddress' : IP,'Port': Port,'Map': Map, 'Query': Query}
                        if 'EncryptionToken' in Query:
                            if not Query['EncryptionToken'].split(':')[1] in versions[Build]['Matches']:
                                versions[Build]['Matches'][Query['EncryptionToken'].split(':')[1]] = {
                                    'InPackets': [],
                                    'OutPackets': [],
                                    'ServerAddress' : IP,
                                    'Port': Port,
                                    'Map': Map,
                                    'SessionID': Query['EncryptionToken'].split(':')[1],
                                    'AccountID': Query['EncryptionToken'].split(':')[0],
                                    'PacketsFound': os.path.exists(f"packets/{Query['EncryptionToken'].split(':')[1]}.json"),
                                    'Packets': []
                                }
                                pkts = json.loads(open(f"packets/{Query['EncryptionToken'].split(':')[1]}.json").read())
                                CurrentPackets = {'InPackets': [], 'OutPackets': []}
                                for pkt in pkts:
                                    if pkt['from_server']:
                                        CurrentPackets['InPackets'].append(pkt['payload'])
                                    else:
                                        CurrentPackets['OutPackets'].append(pkt['payload'])
                                CurrentSessionID = Query['EncryptionToken'].split(':')[1]
                    elif LogSubType == 'UChannel':
                        pass
                    elif LogSubType == 'NetworkFailure':
                        pass
                    elif LogSubType == 'Error':
                        pass
                elif CategoryName == 'LogNetTraffic':
                    if LogSubType == 'VeryVerbose':
                        if 'VeryVerbose: Sending:' in line:
                            PacketIdx = len(versions[Build]['Matches'][CurrentSessionID]['OutPackets'])
                            versions[Build]['Matches'][CurrentSessionID]['OutPackets'].append({'Payload': CurrentPackets["OutPackets"][PacketIdx], 'Bunches': []})
                        elif 'VeryVerbose: SetChannelActor:' in line:
                            Actor_Type = line.split(' Actor: ')[1].split(' ')[0]
                            Actor_Path = line.split(' Actor: ')[1].split(' ')[1].split('.')[0]
                            Actor_NetGUID = line.split('NetGUID: ')[1]

                            if Actor_Type == 'FortPickupAthena':
                                pass
                    elif LogSubType == 'Verbose':
                        if ': Received ' in line:
                            PacketIdx = len(versions[Build]['Matches'][CurrentSessionID]['InPackets'])
                            versions[Build]['Matches'][CurrentSessionID]['InPackets'].append({'Payload': CurrentPackets["InPackets"][PacketIdx], 'Bunches': []})
                    elif 'Bunch Create ' in line:
                        pass
                    elif 'Channel Actor ' in line:
                        pass
                    elif 'Channel ' in line and ' ack timeout); resending ' in line:
                        pass
                    elif 'Creating Replicator' in line:
                        pass
                    elif 'Replicate' in line:
                        Actor = '_'.join(line.split('Replicate ')[1].split(', ')[0].split('_')[:-1])
                    elif 'Sent RPC: ' in line:
                        # https://github.com/EpicGames/UnrealEngine/blob/2bf1a5b83a7076a0fd275887b373f8ec9e99d431/Engine/Source/Runtime/Engine/Private/NetDriver.cpp#L2319
                        RPC_Type = line.split('Sent RPC: ')[1].split(' ')[0]
                        RPC_Path = line.split('Sent RPC: ')[1].split(' ')[1].split('.')[0]
                        RPC_Function_Name = line.split('Sent RPC: ')[1].split(' ')[1].split('::')[1].split(' ')[0]
                        RPC_Length = line.split('[')[1].split(' bytes')[0]

                        if not RPC_Type in RPC_Functions:
                            RPC_Functions[RPC_Type] = []

                        if not RPC_Function_Name in RPC_Functions[RPC_Type]:
                            RPC_Functions[RPC_Type].append(RPC_Function_Name)

                        versions[Build]['Matches'][CurrentSessionID]['InPackets'][len(versions[Build]['Matches'][CurrentSessionID]['InPackets']) - 1]['Bunches'].append({
                            'RPC_Type': RPC_Type,
                            'RPC_Path': RPC_Path,
                            'RPC_Function_Name': RPC_Function_Name
                        })
                        
                        if RPC_Type == 'Athena_PlayerController_C':       
                            if RPC_Function_Name == 'ServerUpdateMultipleLevelsVisibility':
                                pass
                            elif RPC_Function_Name == 'ServerUpdateLevelVisibility':
                                pass
                            elif RPC_Function_Name == 'ServerReadyToStartMatch':
                                pass
                            elif RPC_Function_Name == 'ServerThankBusDriver':
                                pass
                        elif RPC_Type == 'UACNetworkComponent':
                            if RPC_Function_Name == 'SendPacketToServer':
                                pass
                        elif RPC_Type == 'FortAbilitySystemComponentAthena':
                            pass
                        elif RPC_Type == 'PlayerPawn_Athena_C':
                            if RPC_Function_Name == 'ServerMovePacked':
                                pass
                        elif RPC_Type == 'FortPlayerStateAthena':
                            if RPC_Function_Name == 'Server_SetCanEditCreativeIsland':
                                pass
                            elif RPC_Function_Name == 'ServerPlayEmoteItem':
                                pass
                        elif RPC_Type == 'FortBroadcastRemoteClientInfo':   
                            pass
                        elif RPC_Type == 'B_Athena_Pickaxe_Generic_C':      
                            pass
                        elif RPC_Type == 'B_Melee_Impact_Pickaxe_Athena_StarWand_C':
                            pass
                        elif RPC_Type == 'B_Prj_Bullet_Sniper_C':
                            pass
                        elif RPC_Type == 'AthenaMarkerComponent':
                            if RPC_Function_Name == 'ServerAddMapMarker':
                                pass
                        elif RPC_Type == 'B_Pistol_Vigilante_Athena_C':
                            pass
                        elif RPC_Type == 'Prop_TirePile_03_C':
                            pass
                        elif RPC_Type == 'B_Rifle_Sniper_Suppressed_Athena_C':
                            pass
                        elif RPC_Type == 'B_ConsumableSmall_HalfShield_Athena_C':
                            pass
                        elif RPC_Type == 'FortControllerComponent_Aircraft':
                            if RPC_Function_Name == 'ServerAttemptAircraftJump':
                                pass
                        elif RPC_Type == 'FortControllerComponent_Interaction':
                            pass
                        elif RPC_Type == 'Prop_TirePile_04_C':
                            pass
                        elif RPC_Type == 'B_FloppingRabbit_Weap_Athena_C':
                            pass
                        elif RPC_Type == 'Prop_TirePile_01_C':
                            pass
                        elif RPC_Type == 'B_Shotgun_Heavy_Athena_C':
                            pass
                        elif RPC_Type == 'B_PetrolWeapon_C':
                            pass
                        elif RPC_Type == 'B_Shotgun_Charge_Athena_C':
                            pass
                        elif RPC_Type == 'B_Assault_Auto_Athena_C':
                            pass
                        elif RPC_Type == 'B_Grenade_Shockwave_Athena_C':
                            pass
                        elif RPC_Type == 'BP_ZeroPoint_2Point0_C':
                            pass
                        elif RPC_Type == 'BP_IO_Slider_C':
                            if RPC_Function_Name == 'OpenDoors':
                                pass
                        elif RPC_Type == 'B_Prj_Athena_Consumable_Thrown_ShieldSmall_C':
                            pass
                        elif RPC_Type == 'B_ConsumableSmall_MiniShield_Athena_C':
                            pass
                        elif RPC_Type == 'BGA_Petrol_Pickup_C':
                            pass
                        elif RPC_Type == 'SR_Valet_C':
                            pass
                        elif RPC_Type == 'Valet_SportsCar_Vehicle_C':
                            pass
                        elif RPC_Type == 'B_HappyGhost_Athena_C':
                            pass
                        elif RPC_Type == 'B_Pistol_Light_PDW_Athena_C':
                            pass
                        elif RPC_Type == 'B_Pistol_AutoHeavy_Athena_Supp_Child_C':
                            pass
                        elif RPC_Type == 'GA_Athena_Consumable_ThrowWithTrajectory_Parent_C':
                            pass
                        elif RPC_Type == 'Valet_BasicTruck_Vehicle_C':
                            pass
                        elif RPC_Type == 'AthenaSupplyDrop_C':
                            pass
                        elif RPC_Type == 'BGA_Athena_SCMachine_C':
                            pass
                        elif RPC_Type == 'Prj_Athena_Consumable_Thrown_Coconut_C':
                            pass
                        elif RPC_Type == 'B_Assault_Heavy_Athena_C':
                            pass
                        elif RPC_Type == 'B_Assault_PistolCaliber_AR_Athena_C':
                            pass
                        elif RPC_Type == 'BGA_Athena_FlopperSpawn_World_C':
                            pass
                        elif RPC_Type == 'MeatballVehicle_L_C':
                            pass
                        elif RPC_Type == 'B_Meatball_Launcher_Athena_C':
                            pass
                        elif RPC_Type == 'Prj_Athena_HappyGhost_C':
                            pass
                        elif RPC_Type == 'B_Athena_HappyGhost_Wire_C':
                            pass
                        elif RPC_Type == 'Prj_Athena_FloppingRabbit_HighTier_C':
                            pass
                        elif RPC_Type == 'B_Prj_Meatball_Missile_C':
                            pass
                        elif RPC_Type == 'SR_Core_C':
                            pass
                        elif RPC_Type == 'B_Athena_FloppingRabbit_Wire_HighTier_C':
                            pass
                        elif RPC_Type == 'B_Prj_Athena_Consumable_Thrown_FlopperShield_C':
                            pass
                        elif RPC_Type == 'Prop_BouncyUmbrella_C_C':
                            pass
                        elif RPC_Type == 'B_Flopper_Weap_Athena_C':
                            pass
                        elif RPC_Type == 'NPC_Pawn_SpicySake_Parent_C':
                            pass
                        elif RPC_Type == 'GA_SurfaceChange_Sand_C':
                            pass
                        elif RPC_Type == 'Apollo_GasPump_Valet_C':
                            pass
                        elif RPC_Type == 'Valet_BasicCar_Vehicle_C':
                            pass
                        elif RPC_Type == 'B_Rifle_Sniper_Athena_HighTier_C':
                            pass
                        elif RPC_Type == 'B_Prj_Athena_Consumable_Thrown_Shields_C':
                            pass
                        elif RPC_Type == 'Athena_Prop_SilkyBingo_C':
                            pass
                        elif RPC_Type == 'Prj_Athena_FloppingRabbit_C':
                            pass
                        elif RPC_Type == 'B_Prj_Athena_Consumable_Thrown_Medkit_C':
                            pass
                        elif RPC_Type == 'Valet_SportsCar_Vehicle_Upgrade_C':
                            pass
                        elif RPC_Type == 'BP_BountyBoard_C':
                            pass
                        elif RPC_Type == 'Prop_BouncyUmbrella_A_C':
                            pass
                        elif RPC_Type == 'B_Rifle_Sniper_Athena_C':
                            pass
                        elif RPC_Type == 'B_ChillBronco_Athena_C':
                            pass
                        elif RPC_Type == 'B_Shotgun_HighSemiAuto_Athena_C':
                            pass
                        else:
                            print(f'Unknown RPC_Type: {RPC_Type}')

                    elif LogSubType == 'UActorChannel':
                        if 'UActorChannel::ReadContentBlockHeader' in line:
                            pass
                    elif 'LogNetTraffic:       Actor' in line:
                        pass
                    else:
                        if 'Created channel ' in line and 'of type ' in line:
                            pass
                        else:
                            pass
                elif CategoryName == 'LogWorld':
                    if 'Bringing World' in line:
                        pass
                    elif LogSubType == 'UWorld':
                        pass
                elif CategoryName == 'LogLoad':
                    if LogSubType == 'LoadMap':
                        try:
                            IP = line.split('LogLoad: LoadMap: ')[1].split(':')[0]
                            Port = line.split('LogLoad: LoadMap: ')[1].split(':')[1].split('/')[0]
                            Map = line.split(f'LogLoad: LoadMap: {IP}:{Port}')[1]
                        except:
                            IP = ''
                            Port = ''
                            Map = line.split(f'LogLoad: LoadMap: ')[1]
                        Query = {}
                        if '?' in Map:
                            for q in Map.split('?')[1:]:
                                if '=' in q:
                                    Query[q.split('=')[0]] = q.split('=')[1]
                                else:
                                    Query[q.split('=')[0]] = ''
                            Map = Map.split('?')[0]
                        versions[Build]["Actions"][ActionNumber]['Load'] = {'ServerAddress' : IP,'Port': Port,'Map': Map, 'Query': Query}
                elif CategoryName == 'LogParty':
                    if LogSubType == 'Join party info':
                        if not 'Party' in versions[Build]["Actions"][ActionNumber]:
                            versions[Build]["Actions"][ActionNumber]['Party'] = {'JoinAnalytics': {}}

                        versions[Build]["Actions"][ActionNumber]['Party']['JoinAnalytics']['SourceDisplayName'] = line.split('SourceDisplayName(')[1].split(') ')[0]
                        versions[Build]["Actions"][ActionNumber]['Party']['JoinAnalytics']['PartyId'] = line.split('PartyId(')[1].split(') ')[0]
                        versions[Build]["Actions"][ActionNumber]['Party']['JoinAnalytics']['HasKey'] = line.split('HasKey(')[1].split(') ')[0]
                        versions[Build]["Actions"][ActionNumber]['Party']['JoinAnalytics']['HasPassword'] = line.split('HasPassword(')[1].split(') ')[0]
                        versions[Build]["Actions"][ActionNumber]['Party']['JoinAnalytics']['IsAcceptingMembers'] = line.split('IsAcceptingMembers(')[1].split(') ')[0]
                        versions[Build]["Actions"][ActionNumber]['Party']['JoinAnalytics']['NotAcceptingReason'] = line.split('NotAcceptingReason(')[1].split(') ')[0]
                        versions[Build]["Actions"][ActionNumber]['Party']['JoinAnalytics']['SentTime'] = line.split('SentTime(')[1].split(') ')[0]
                        versions[Build]["Actions"][ActionNumber]['Party']['JoinAnalytics']['ReceivedTime'] = line.split('ReceivedTime(')[1].split(')')[0]
                    elif line.startswith('LogParty:   '):
                        if not 'Party' in versions[Build]["Actions"][ActionNumber]:
                            versions[Build]["Actions"][ActionNumber]['Party'] = {'JoinAnalytics': {}}

                        elif line.startswith('LogParty:   Result: '):
                            versions[Build]["Actions"][ActionNumber]['Party']['JoinAnalytics']['Result'] = line.split('LogParty:   Result: ')[1]
                        elif line.startswith('LogParty:   UserId: '):
                            versions[Build]["Actions"][ActionNumber]['Party']['JoinAnalytics']['UserId'] = line.split('LogParty:   UserId: ')[1]
                        elif line.startswith('LogParty:   PartyId: '):
                            versions[Build]["Actions"][ActionNumber]['Party']['JoinAnalytics']['PartyId'] = line.split('LogParty:   PartyId: ')[1]
                        elif line.startswith('LogParty:   PartyTypeId: '):
                            versions[Build]["Actions"][ActionNumber]['Party']['JoinAnalytics']['PartyTypeId'] = line.split('LogParty:   PartyTypeId: ')[1]
                        elif line.startswith('LogParty:   FriendId: '):
                            versions[Build]["Actions"][ActionNumber]['Party']['JoinAnalytics']['FriendId'] = line.split('LogParty:   FriendId: ')[1]
                        elif line.startswith('LogParty:   LeaderId: '):
                            versions[Build]["Actions"][ActionNumber]['Party']['JoinAnalytics']['LeaderId'] = line.split('LogParty:   LeaderId: ')[1]
                        elif line.startswith('LogParty:   SubGame: '):
                            versions[Build]["Actions"][ActionNumber]['Party']['JoinAnalytics']['SubGame'] = line.split('LogParty:   SubGame: ')[1]
                elif CategoryName == 'LogOnlineParty':
                    pass
                elif CategoryName == 'LogMatchmakingServiceClient':
                    if not 'MatchmakingServiceClient' in versions[Build]["Actions"][ActionNumber]:
                        versions[Build]["Actions"][ActionNumber]['MatchmakingServiceClient'] = {'HandleStatusUpdateMessage': {'Messages': []}, 'HandleQueuedStatusUpdate': [], 'ChangeState': []}
                    # Received
                    if line.startswith('LogMatchmakingServiceClient: Verbose: HandleWebSocketMessage - Received message'):
                        info = {}
                        try:
                            msg = json.loads(line.split('LogMatchmakingServiceClient: Verbose: HandleWebSocketMessage - Received message: "')[1].strip()[:-1])
                            if msg.get('payload'):
                                info = msg['payload']
                        except:
                            info['RawMessage'] = line.split('LogMatchmakingServiceClient: Verbose: HandleWebSocketMessage - Received message: "')[1].strip()[:-1]
                        versions[Build]["Actions"][ActionNumber]['MatchmakingServiceClient']['HandleStatusUpdateMessage']['Messages'].append({
                            **{
                                'Incoming': True,
                                'Outgoing': False
                            },
                            **info
                        })
                    elif line.startswith('LogMatchmakingServiceClient: HandleQueuedStatusUpdate - '):
                        versions[Build]["Actions"][ActionNumber]['MatchmakingServiceClient']['HandleQueuedStatusUpdate'].append({
                            "TicketId": line.split("TicketId: '")[1].split("'")[0],
                            "NumQueuedPlayers": int(line.split('NumQueuedPlayers: ')[1].split(', ')[0]),
                            "EstimatedWaitTime": line.split('EstimatedWaitTime: ')[1]
                        })
                    elif line.startswith('LogMatchmakingServiceClient: ChangeState - '):
                        versions[Build]["Actions"][ActionNumber]['MatchmakingServiceClient']['ChangeState'].append({
                            line.split("LogMatchmakingServiceClient: ChangeState - '")[1].split("' -> ")[0]: line.split("LogMatchmakingServiceClient: ChangeState - '")[1].split("' -> '")[1]
                        })
                elif CategoryName == 'LogDiscordRPC':
                    if line.startswith('LogDiscordRPC: Verbose: FDiscordRPC::UpdatePresence'):
                        if not 'Discord' in versions[Build]["Actions"][ActionNumber]:
                            versions[Build]["Actions"][ActionNumber]['Discord'] = {'Updates': []}

                        versions[Build]["Actions"][ActionNumber]['Discord']['Updates'].append({
                            'State': line.split('LogDiscordRPC: Verbose: FDiscordRPC::UpdatePresence State: ')[1].split(', Details: ')[0],
                            'Details': line.split(', Details:')[1]
                        })
                elif CategoryName == 'LogFort':
                    if LogSubType == 'SetIsDisconnecting':
                        if not 'Fort' in versions[Build]["Actions"][ActionNumber]:
                            versions[Build]["Actions"][ActionNumber]['Fort'] = {}

                        versions[Build]["Actions"][ActionNumber]['Fort']['DisconnectingState'] = {
                            'Old': int(line.split('OldState: ')[1].split(' NewState: ')[0]),
                            'New': int(line.split('NewState: ')[1].strip()),
                        }
                    elif 'Disconnecting' in LogSubType:
                        if not 'Fort' in versions[Build]["Actions"][ActionNumber]:
                            versions[Build]["Actions"][ActionNumber]['Fort'] = {}

                        Reason = line.split(' Disconnecting: 1: DevReason - ')[1]
                        versions[Build]["Actions"][ActionNumber]['Fort']['Disconnecting'] = {
                            'Reason': Reason
                        }
                    elif LogSubType == 'PLAYLIST':
                        if not 'Fort' in versions[Build]["Actions"][ActionNumber]:
                            versions[Build]["Actions"][ActionNumber]['Fort'] = {'Playlists': []}
                        if not 'Playlists' in versions[Build]["Actions"][ActionNumber]['Fort']:
                            versions[Build]["Actions"][ActionNumber]['Fort']['Playlists'] = []

                        versions[Build]["Actions"][ActionNumber]['Fort']['Playlists'].append({
                            'Playlist': "Playlist_" + line.split('Playlist_')[-1].split(' (')[0],
                            'Type': line.split('Playlist_')[-1].split(' (')[1].split(')')[0]
                        })
                elif CategoryName == 'LogMatchAnalytics':
                    if not 'Match' in versions[Build]["Actions"][ActionNumber]: # Analytics
                        versions[Build]["Actions"][ActionNumber]['Match'] = {'Analytics': {'Checkpoints': {}}}
                    
                    if LogSubType == 'DUMPCHECKPOINTS':
                        pass
                    elif LogSubType == 'SessionLength':
                        pass
                    elif LogSubType == 'Checkpoint':
                        versions[Build]["Actions"][ActionNumber]['Match']['Analytics']['Checkpoints'][Result.split(':')[0]] = ':'.join(Result.split(':')[1:]).strip()
                    else:
                        versions[Build]["Actions"][ActionNumber]['Match']['Analytics'][Result.split(' ')[0]] = ':'.join(Result.split(' ')[1:]).strip()
                elif CategoryName == 'LogOnlineGame':
                    if LogSubType == 'Warning':
                        if not 'OnlineGame' in versions[Build]["Actions"][ActionNumber]:
                            versions[Build]["Actions"][ActionNumber]['OnlineGame'] = {}

                        if Result.split(' ')[0] == 'ClientWasKicked':
                            versions[Build]["Actions"][ActionNumber]['OnlineGame']['ClientWasKickedReason'] = Result.split('ClientWasKicked Reason: ')[1]
                elif CategoryName == 'LogOnline':
                    if 'OnXmppPresenceReceived' in line:
                        if not 'XMPP' in versions[Build]["Actions"][ActionNumber]:
                            versions[Build]["Actions"][ActionNumber]['XMPP'] = {'Messages': []}

                        fromJID = line.split('from=')[1].split(' ')[0]
                        Status = line.split(f'{fromJID} [')[1].split(']')[0]
                        Time = line.split(f'{fromJID} [{Status}] [')[1].split(']')[0]
                        Payload = line.split(f'{fromJID} [{Status}] [{Time}] [')[1]

                        try:
                            Payload = json.loads(Payload)
                        except:
                            pass

                        versions[Build]["Actions"][ActionNumber]['XMPP']['Messages'].append({
                            'Incoming': True,
                            'Outgoing': False,
                            'Message': Payload
                        })
                else:
                    pass
                    # print(f'Unknown CategoryName: {CategoryName}')
        except Exception as e:
            pass # print(f'Failed to parse this line: {line} Error: {e}\n')        

    logs_read += 1
    file_count -= 1

max_file_at_once = 10
for file in os.listdir(logs_dir):
    if file_count >= max_file_at_once:
        time.sleep(0.5)
    Thread(target=parse, args=(file,)).start()
    file_count += 1

while (logs_read != len(os.listdir(logs_dir))):
    time.sleep(1)

# If we do not do it at the end there might be issues if logs have to same Build
# Remove all unused actions
for Build in list(versions.keys()):
    for k, v in dict(versions[Build]["Actions"]).items():
        if not v:
            del versions[Build]["Actions"][k]

open('Versions.json', 'w+').write(json.dumps(versions, indent=2))
print(f'Total Versions Parsed: {len(versions)}')
open('RPC_Functions.json', 'w+').write(json.dumps(RPC_Functions, indent=2))