/*
 * Gateway sleep energy comparison example for LoRaWAN.
 *
 * Compares an always-on gateway vs a duty-cycled gateway that sleeps
 * outside scheduled transmission windows. Uses SF clustering so different
 * SFs can transmit in parallel within the same window.
 */

#include "ns3/command-line.h"
#include "ns3/constant-position-mobility-model.h"
#include "ns3/double.h"
#include "ns3/file-helper.h"
#include "ns3/log.h"
#include "ns3/lora-channel.h"
#include "ns3/lora-helper.h"
#include "ns3/lora-net-device.h"
#include "ns3/lora-phy-helper.h"
#include "ns3/lorawan-mac-helper.h"
#include "ns3/mobility-helper.h"
#include "ns3/node-container.h"
#include "ns3/periodic-sender-helper.h"
#include "ns3/position-allocator.h"
#include "ns3/random-variable-stream.h"
#include "ns3/rng-seed-manager.h"
#include "ns3/simulator.h"
#include "ns3/string.h"
#include "ns3/class-a-end-device-lorawan-mac.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <unordered_set>
#include <vector>

using namespace ns3;
using namespace lorawan;

NS_LOG_COMPONENT_DEFINE("LoraGatewaySleepEnergyExample");

namespace
{

struct GatewayEnergyResult
{
    double totalJ = 0.0;
    double idleJ = 0.0;
    double sleepJ = 0.0;
    double rxJ = 0.0;
    double idleSeconds = 0.0;
    double sleepSeconds = 0.0;
    double rxSeconds = 0.0;
    uint32_t packetsSent = 0;
    uint32_t packetsReceived = 0;
};

struct LossBreakdown
{
    uint32_t overlapCollision = 0;
    uint32_t crossSfInterference = 0;
    uint32_t gatewaySleepingMissedWindow = 0;
    uint32_t insufficientReceiveWindow = 0;
    uint32_t sfChannelContention = 0;
    uint32_t underSensitivity = 0;
    uint32_t gatewayTxBusy = 0;
    uint32_t timingMismatch = 0;
};

class GatewayEnergyTracker
{
  public:
    enum class State
    {
        SLEEP,
        IDLE,
        RX
    };

    GatewayEnergyTracker(double supplyV, double idleA, double sleepA, double rxA, Time wakeupTime)
        : m_supplyV(supplyV),
          m_idleA(idleA),
          m_sleepA(sleepA),
          m_rxA(rxA),
          m_wakeupTime(wakeupTime),
          m_state(State::IDLE),
          m_lastUpdate(Seconds(0)),
          m_awake(true)
    {
    }

    void SetAwake(bool awake)
    {
        if (m_awake == awake)
        {
            return;
        }
        m_awake = awake;
        if (!m_awake)
        {
            Transition(State::SLEEP);
        }
        else
        {
            Transition(m_rxCount > 0 ? State::RX : State::IDLE);
            m_wakeupCount++;
        }
    }

    void OnRxBegin(Ptr<const Packet> /*packet*/)
    {
        if (!m_awake)
        {
            return;
        }
        m_rxCount++;
        Transition(State::RX);
    }

    void OnRxEnd(Ptr<const Packet> /*packet*/)
    {
        if (!m_awake)
        {
            return;
        }
        if (m_rxCount > 0)
        {
            m_rxCount--;
        }
        if (m_rxCount == 0)
        {
            Transition(State::IDLE);
        }
    }

    void Finalize()
    {
        Transition(m_state);
    }

    GatewayEnergyResult GetResult() const
    {
        GatewayEnergyResult result;
        result.totalJ = m_totalJ;
        result.idleJ = m_idleJ;
        result.sleepJ = m_sleepJ;
        result.rxJ = m_rxJ;
        result.idleSeconds = m_idleSeconds;
        result.sleepSeconds = m_sleepSeconds;
        result.rxSeconds = m_rxSeconds;
        return result;
    }

    uint32_t GetWakeupCount() const
    {
        return m_wakeupCount;
    }

  private:
    void Transition(State next)
    {
        Time now = Simulator::Now();
        Time delta = now - m_lastUpdate;
        double seconds = delta.GetSeconds();
        if (seconds > 0.0)
        {
            switch (m_state)
            {
            case State::SLEEP:
                m_sleepJ += seconds * m_supplyV * m_sleepA;
                m_sleepSeconds += seconds;
                break;
            case State::IDLE:
                m_idleJ += seconds * m_supplyV * m_idleA;
                m_idleSeconds += seconds;
                break;
            case State::RX:
                m_rxJ += seconds * m_supplyV * m_rxA;
                m_rxSeconds += seconds;
                break;
            }
            m_totalJ = m_idleJ + m_sleepJ + m_rxJ;
        }

        m_state = next;
        m_lastUpdate = now;
    }

    double m_supplyV;
    double m_idleA;
    double m_sleepA;
    double m_rxA;
    Time m_wakeupTime;

    State m_state;
    Time m_lastUpdate;
    bool m_awake;
    uint32_t m_rxCount = 0;
    uint32_t m_wakeupCount = 0;

    double m_totalJ = 0.0;
    double m_idleJ = 0.0;
    double m_sleepJ = 0.0;
    double m_rxJ = 0.0;
    double m_idleSeconds = 0.0;
    double m_sleepSeconds = 0.0;
    double m_rxSeconds = 0.0;
};

struct ScenarioResult
{
    GatewayEnergyResult energy;
    LossBreakdown losses;
    double pdr = 0.0;
    uint32_t sent = 0;
    uint32_t received = 0;
    std::array<uint32_t, 6> sfHistogram{{0, 0, 0, 0, 0, 0}};
    uint32_t sf12OutOfRange = 0;
};

class GatewayOutcomeTracker
{
  public:
    void OnSuccess(Ptr<const Packet> packet, uint32_t)
    {
        m_completed.insert(packet->GetUid());
    }

    void OnInterference(Ptr<const Packet> packet, uint32_t)
    {
        m_completed.insert(packet->GetUid());

        LoraTag tag;
        uint8_t packetSf = 0;
        uint8_t destroyedBy = 0;
        if (packet->PeekPacketTag(tag))
        {
            packetSf = tag.GetSpreadingFactor();
            destroyedBy = tag.GetDestroyedBy();
        }

        if (packetSf != 0 && destroyedBy == packetSf)
        {
            m_losses.overlapCollision++;
        }
        else
        {
            m_losses.crossSfInterference++;
        }
    }

    void OnUnderSensitivity(Ptr<const Packet> packet, uint32_t)
    {
        if (MarkUnique(packet))
        {
            m_losses.underSensitivity++;
        }
    }

    void OnNoMoreReceivers(Ptr<const Packet> packet, uint32_t)
    {
        if (MarkUnique(packet))
        {
            m_losses.sfChannelContention++;
        }
    }

    void OnGatewayTxBusy(Ptr<const Packet> packet, uint32_t)
    {
        if (MarkUnique(packet))
        {
            m_losses.gatewayTxBusy++;
        }
    }

    void OnSleepAtStart(Ptr<const Packet> packet, uint32_t)
    {
        if (MarkUnique(packet))
        {
            m_losses.gatewaySleepingMissedWindow++;
        }
    }

    void OnSleepAbort(Ptr<const Packet> packet, uint32_t)
    {
        if (MarkUnique(packet))
        {
            m_losses.insufficientReceiveWindow++;
        }
    }

    LossBreakdown GetLosses() const
    {
        return m_losses;
    }

  private:
    bool MarkUnique(Ptr<const Packet> packet)
    {
        auto [it, inserted] = m_completed.insert(packet->GetUid());
        return inserted;
    }

    LossBreakdown m_losses;
    std::unordered_set<uint64_t> m_completed;
};

static void
WritePositions(const std::string& path, Ptr<Node> gateway, const NodeContainer& endDevices)
{
    if (path.empty())
    {
        return;
    }

    std::ofstream out(path);
    out << "type,nodeId,x,y,z\n";

    Ptr<MobilityModel> gwMob = gateway->GetObject<MobilityModel>();
    if (gwMob)
    {
        Vector pos = gwMob->GetPosition();
        out << "gateway," << gateway->GetId() << "," << pos.x << "," << pos.y << "," << pos.z
            << "\n";
    }

    for (uint32_t i = 0; i < endDevices.GetN(); ++i)
    {
        Ptr<Node> node = endDevices.Get(i);
        Ptr<MobilityModel> mob = node->GetObject<MobilityModel>();
        if (!mob)
        {
            continue;
        }
        Vector pos = mob->GetPosition();
        out << "end_device," << node->GetId() << "," << pos.x << "," << pos.y << "," << pos.z
            << "\n";
    }
}

static void
SetGatewaySleepWindow(Ptr<GatewayLoraPhy> gwPhy,
                      GatewayEnergyTracker* tracker,
                      bool sleepEnabled,
                      Time wakeTime,
                      Time sleepTime)
{
    if (!sleepEnabled)
    {
        return;
    }

    Simulator::Schedule(wakeTime, [gwPhy, tracker]() {
        gwPhy->SetSleepMode(false);
        tracker->SetAwake(true);
    });

    Simulator::Schedule(sleepTime, [gwPhy, tracker]() {
        gwPhy->SetSleepMode(true);
        tracker->SetAwake(false);
    });
}

static ScenarioResult
RunScenario(bool sleepEnabled,
            uint32_t nDevices,
            double radiusMeters,
            Time period,
            Time slotSpacing,
            Time wakeupTime,
            Time simTime,
            double supplyV,
            double idleA,
            double sleepA,
            double rxA,
            const std::string& positionsCsv)
{
    // Create the channel
    Ptr<LogDistancePropagationLossModel> loss = CreateObject<LogDistancePropagationLossModel>();
    loss->SetPathLossExponent(3.76);
    loss->SetReference(1, 7.7);
    Ptr<PropagationDelayModel> delay = CreateObject<ConstantSpeedPropagationDelayModel>();
    Ptr<LoraChannel> channel = CreateObject<LoraChannel>(loss, delay);

    // Mobility
    MobilityHelper mobility;
    Ptr<ListPositionAllocator> gwPosition = CreateObject<ListPositionAllocator>();
    gwPosition->Add(Vector(0, 0, 0));
    mobility.SetPositionAllocator(gwPosition);
    mobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");

    // Helpers
    LoraPhyHelper phyHelper;
    phyHelper.SetChannel(channel);
    LorawanMacHelper macHelper;
    LoraHelper helper;
    helper.EnablePacketTracking();

    // End devices
    NodeContainer endDevices;
    endDevices.Create(nDevices);

    Ptr<UniformDiscPositionAllocator> edPositions = CreateObject<UniformDiscPositionAllocator>();
    edPositions->SetRho(radiusMeters);
    mobility.SetPositionAllocator(edPositions);
    mobility.Install(endDevices);

    phyHelper.SetDeviceType(LoraPhyHelper::ED);
    macHelper.SetDeviceType(LorawanMacHelper::ED_A);
    NetDeviceContainer endDevicesNetDevices = helper.Install(phyHelper, macHelper, endDevices);

    // Gateway
    NodeContainer gateways;
    gateways.Create(1);
    mobility.SetPositionAllocator(gwPosition);
    mobility.Install(gateways);

    WritePositions(positionsCsv, gateways.Get(0), endDevices);

    phyHelper.SetDeviceType(LoraPhyHelper::GW);
    macHelper.SetDeviceType(LorawanMacHelper::GW);
    helper.Install(phyHelper, macHelper, gateways);

    Ptr<Node> gatewayNode = gateways.Get(0);
    Ptr<LoraNetDevice> gwDevice = DynamicCast<LoraNetDevice>(gatewayNode->GetDevice(0));
    NS_ASSERT_MSG(gwDevice, "Failed to get gateway LoraNetDevice");
    Ptr<GatewayLoraPhy> gwPhy = DynamicCast<GatewayLoraPhy>(gwDevice->GetPhy());
    NS_ASSERT_MSG(gwPhy, "Failed to get gateway LoraPhy");
    NS_ASSERT_MSG(gatewayNode->GetObject<MobilityModel>(),
                  "Gateway node has no MobilityModel");

    // Assign SF/DR based on link budget (RSSI sensitivity) and cluster by SF for scheduling
    std::vector<int> drDistribution =
        LorawanMacHelper::SetSpreadingFactorsUp(endDevices, gateways, channel);
    std::array<std::vector<uint32_t>, 6> sfGroups;
    std::array<uint32_t, 6> sfHistogram{{0, 0, 0, 0, 0, 0}};
    const uint8_t packetSize = 10;
    Ptr<Packet> toaPacket = Create<Packet>(packetSize);
    uint8_t maxSf = 7;
    for (uint32_t i = 0; i < nDevices; ++i)
    {
        Ptr<LoraNetDevice> dev = DynamicCast<LoraNetDevice>(endDevicesNetDevices.Get(i));
        NS_ASSERT_MSG(dev, "Failed to get end-device LoraNetDevice");
        Ptr<ClassAEndDeviceLorawanMac> mac = DynamicCast<ClassAEndDeviceLorawanMac>(dev->GetMac());
        NS_ASSERT_MSG(mac, "Failed to get ClassAEndDeviceLorawanMac");
        uint8_t sf = mac->GetSfFromDataRate(mac->GetDataRate());
        if (sf < 7 || sf > 12)
        {
            sf = 12;
        }
        sfHistogram.at(sf - 7)++;
        sfGroups.at(sf - 7).push_back(i);
        maxSf = std::max(maxSf, sf);
    }

    LoraTxParameters maxParams;
    maxParams.sf = maxSf;
    maxParams.lowDataRateOptimizationEnabled = LoraPhy::GetTSym(maxParams) > MilliSeconds(16);
    Time maxToA = LoraPhy::GetOnAirTime(toaPacket, maxParams);

    // Applications
    PeriodicSenderHelper periodicSenderHelper;
    periodicSenderHelper.SetPacketSize(packetSize);
    periodicSenderHelper.SetPeriod(period);
    ApplicationContainer apps = periodicSenderHelper.Install(endDevices);

    // Align initial sends in clustered windows: same slot index -> same time for different SFs
    uint32_t maxGroupSize = 0;
    for (const auto& group : sfGroups)
    {
        maxGroupSize = std::max<uint32_t>(maxGroupSize, group.size());
    }
    if (maxGroupSize == 0)
    {
        maxGroupSize = 1;
    }

    Time effectiveSlotSpacing = std::max(slotSpacing, maxToA);
    Time windowStart = Seconds(1.0);
    for (uint32_t sfIndex = 0; sfIndex < sfGroups.size(); ++sfIndex)
    {
        const auto& group = sfGroups.at(sfIndex);
        for (uint32_t idx = 0; idx < group.size(); ++idx)
        {
            Ptr<Application> app = apps.Get(group.at(idx));
            Ptr<PeriodicSender> sender = DynamicCast<PeriodicSender>(app);
            if (sender)
            {
                Time offset = effectiveSlotSpacing * idx;
                sender->SetInitialDelay(windowStart + offset);
            }
        }
    }

    // Gateway energy tracking
    GatewayEnergyTracker tracker(supplyV, idleA, sleepA, rxA, wakeupTime);
    GatewayOutcomeTracker outcomeTracker;
    gwPhy->TraceConnectWithoutContext("PhyRxBegin",
                                      MakeCallback(&GatewayEnergyTracker::OnRxBegin, &tracker));
    gwPhy->TraceConnectWithoutContext("PhyRxEnd",
                                      MakeCallback(&GatewayEnergyTracker::OnRxEnd, &tracker));
    gwPhy->TraceConnectWithoutContext("ReceivedPacket",
                                      MakeCallback(&GatewayOutcomeTracker::OnSuccess,
                                                   &outcomeTracker));
    gwPhy->TraceConnectWithoutContext("LostPacketBecauseInterference",
                                      MakeCallback(&GatewayOutcomeTracker::OnInterference,
                                                   &outcomeTracker));
    gwPhy->TraceConnectWithoutContext("LostPacketBecauseUnderSensitivity",
                                      MakeCallback(&GatewayOutcomeTracker::OnUnderSensitivity,
                                                   &outcomeTracker));
    gwPhy->TraceConnectWithoutContext("LostPacketBecauseNoMoreReceivers",
                                      MakeCallback(&GatewayOutcomeTracker::OnNoMoreReceivers,
                                                   &outcomeTracker));
    gwPhy->TraceConnectWithoutContext("NoReceptionBecauseTransmitting",
                                      MakeCallback(&GatewayOutcomeTracker::OnGatewayTxBusy,
                                                   &outcomeTracker));
    gwPhy->TraceConnectWithoutContext("LostPacketBecauseSleep",
                                      MakeCallback(&GatewayOutcomeTracker::OnSleepAtStart,
                                                   &outcomeTracker));
    gwPhy->TraceConnectWithoutContext("LostPacketBecauseSleepAbort",
                                      MakeCallback(&GatewayOutcomeTracker::OnSleepAbort,
                                                   &outcomeTracker));

    // Schedule gateway sleep windows
    Time windowLength = effectiveSlotSpacing * maxGroupSize;
    Time guard = effectiveSlotSpacing;
    uint32_t numWindows = static_cast<uint32_t>(simTime.GetSeconds() / period.GetSeconds()) + 1;

    for (uint32_t w = 0; w < numWindows; ++w)
    {
        Time start = windowStart + period * w;
        Time wakeTime = start - wakeupTime;
        if (wakeTime.IsNegative())
        {
            wakeTime = Seconds(0);
        }
        Time sleepTime = start + windowLength + guard;
        SetGatewaySleepWindow(gwPhy, &tracker, sleepEnabled, wakeTime, sleepTime);
    }

    Simulator::Stop(simTime);
    Simulator::Run();

    // Packet delivery metrics
    LoraPacketTracker& trackerHelper = helper.GetPacketTracker();
    std::vector<int> stats = trackerHelper.CountPhyPacketsPerGw(Seconds(0), simTime, gatewayNode->GetId());
    uint32_t totalSent = stats.at(0);
    uint32_t totalReceived = stats.at(1);
    double pdr = (totalSent > 0) ? static_cast<double>(totalReceived) / totalSent : 0.0;

    tracker.Finalize();
    GatewayEnergyResult energy = tracker.GetResult();
    energy.packetsSent = totalSent;
    energy.packetsReceived = totalReceived;

    Simulator::Destroy();

    ScenarioResult result;
    result.energy = energy;
    result.losses = outcomeTracker.GetLosses();
    result.pdr = pdr;
    result.sent = totalSent;
    result.received = totalReceived;
    result.sfHistogram = sfHistogram;
    result.sf12OutOfRange = (drDistribution.size() >= 7 && drDistribution.at(6) > 0)
                                ? static_cast<uint32_t>(drDistribution.at(6))
                                : 0;
    return result;
}

} // namespace

int
main(int argc, char* argv[])
{
    uint32_t nDevices = 30;
    double radiusMeters = 1000.0;
    double supplyV = 5.0;
    double idleA = 0.542;
    double sleepA = 0.1;
    double rxA = 0.65;
    double periodMinutes = 30.0;
    double slotSpacingSeconds = 2.0;
    double wakeupSeconds = 4.0;
    double simHours = 6.0;
    uint32_t seed = 1;
    uint32_t run = 1;
    std::string outCsv = "gateway-energy-results.csv";
    std::string positionsCsv;

    CommandLine cmd;
    cmd.AddValue("nDevices", "Number of end devices", nDevices);
    cmd.AddValue("radius", "Radius of deployment area (meters)", radiusMeters);
    cmd.AddValue("supplyV", "Gateway supply voltage (V)", supplyV);
    cmd.AddValue("idleA", "Gateway idle current (A)", idleA);
    cmd.AddValue("sleepA", "Gateway sleep current (A)", sleepA);
    cmd.AddValue("rxA", "Gateway RX current (A)", rxA);
    cmd.AddValue("periodMinutes", "Send period in minutes", periodMinutes);
    cmd.AddValue("slotSpacing", "Slot spacing in seconds", slotSpacingSeconds);
    cmd.AddValue("wakeupSeconds", "Wakeup time in seconds", wakeupSeconds);
    cmd.AddValue("simHours", "Simulation duration in hours", simHours);
    cmd.AddValue("seed", "RNG seed", seed);
    cmd.AddValue("run", "RNG run number", run);
    cmd.AddValue("outCsv", "Output CSV path", outCsv);
    cmd.AddValue("positionsCsv", "Optional positions CSV path", positionsCsv);
    cmd.Parse(argc, argv);

    Time period = Minutes(periodMinutes);
    Time slotSpacing = Seconds(slotSpacingSeconds);
    Time wakeupTime = Seconds(wakeupSeconds);
    Time simTime = Hours(simHours);

    RngSeedManager::SetSeed(seed);
    RngSeedManager::SetRun(run);
    ScenarioResult alwaysOn = RunScenario(false,
                                          nDevices,
                                          radiusMeters,
                                          period,
                                          slotSpacing,
                                          wakeupTime,
                                          simTime,
                                          supplyV,
                                          idleA,
                                          sleepA,
                                          rxA,
                                          positionsCsv);
    RngSeedManager::SetSeed(seed);
    RngSeedManager::SetRun(run);
    ScenarioResult sleepEnabled = RunScenario(true,
                                              nDevices,
                                              radiusMeters,
                                              period,
                                              slotSpacing,
                                              wakeupTime,
                                              simTime,
                                              supplyV,
                                              idleA,
                                              sleepA,
                                              rxA,
                                              std::string());

    std::ofstream out(outCsv);
    out << "scenario,totalJ,idleJ,sleepJ,rxJ,idleSeconds,sleepSeconds,rxSeconds,packetsSent,"
        << "packetsReceived,pdr,sf7,sf8,sf9,sf10,sf11,sf12,sf12OutOfRange,overlapCollision,"
        << "crossSfInterference,gatewaySleepingMissedWindow,insufficientReceiveWindow,"
        << "sfChannelContention,underSensitivity,gatewayTxBusy,timingMismatch\n";
    out << "always_on," << alwaysOn.energy.totalJ << "," << alwaysOn.energy.idleJ << ","
        << alwaysOn.energy.sleepJ << "," << alwaysOn.energy.rxJ << ","
        << alwaysOn.energy.idleSeconds << "," << alwaysOn.energy.sleepSeconds << ","
        << alwaysOn.energy.rxSeconds << "," << alwaysOn.sent << "," << alwaysOn.received << ","
        << alwaysOn.pdr << "," << alwaysOn.sfHistogram.at(0) << "," << alwaysOn.sfHistogram.at(1)
        << "," << alwaysOn.sfHistogram.at(2) << "," << alwaysOn.sfHistogram.at(3) << ","
        << alwaysOn.sfHistogram.at(4) << "," << alwaysOn.sfHistogram.at(5) << ","
        << alwaysOn.sf12OutOfRange << "," << alwaysOn.losses.overlapCollision << ","
        << alwaysOn.losses.crossSfInterference << ","
        << alwaysOn.losses.gatewaySleepingMissedWindow << ","
        << alwaysOn.losses.insufficientReceiveWindow << ","
        << alwaysOn.losses.sfChannelContention << "," << alwaysOn.losses.underSensitivity << ","
        << alwaysOn.losses.gatewayTxBusy << "," << alwaysOn.losses.timingMismatch << "\n";
    out << "sleep_enabled," << sleepEnabled.energy.totalJ << "," << sleepEnabled.energy.idleJ
        << "," << sleepEnabled.energy.sleepJ << "," << sleepEnabled.energy.rxJ << ","
        << sleepEnabled.energy.idleSeconds << "," << sleepEnabled.energy.sleepSeconds << ","
        << sleepEnabled.energy.rxSeconds << "," << sleepEnabled.sent << ","
        << sleepEnabled.received << "," << sleepEnabled.pdr << ","
        << sleepEnabled.sfHistogram.at(0) << "," << sleepEnabled.sfHistogram.at(1) << ","
        << sleepEnabled.sfHistogram.at(2) << "," << sleepEnabled.sfHistogram.at(3) << ","
        << sleepEnabled.sfHistogram.at(4) << "," << sleepEnabled.sfHistogram.at(5) << ","
        << sleepEnabled.sf12OutOfRange << "," << sleepEnabled.losses.overlapCollision << ","
        << sleepEnabled.losses.crossSfInterference << ","
        << sleepEnabled.losses.gatewaySleepingMissedWindow << ","
        << sleepEnabled.losses.insufficientReceiveWindow << ","
        << sleepEnabled.losses.sfChannelContention << ","
        << sleepEnabled.losses.underSensitivity << "," << sleepEnabled.losses.gatewayTxBusy << ","
        << sleepEnabled.losses.timingMismatch << "\n";
    out.close();

    return 0;
}
