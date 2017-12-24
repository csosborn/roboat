#ifndef ROBOATSTATEMACHINE_H
#define ROBOATSTATEMACHINE_H


namespace Roboat {
    
    template <typename StateEnum, typename MachineC>
    class StateMachine {
        StateEnum state;
        StateEnum nextState;
        uint32_t lastUpdateTime;
        uint32_t nextUpdateTime;
        uint32_t stateEntryTime;
        const char * name;

    protected:
        void goToState(StateEnum newState, uint32_t transitionDelay = 0);
        
    public:
        StateMachine(StateEnum initialState, const char * machineName);
        
        // Advance the state machine. Returns true if the update results in any
        // change in external state, false if the update is a noop or affects only
        // state internal to the RoboatAHRS instance.
        bool advance(const uint32_t now);
        
        // The time spent so far in the current state (in us).
        uint32_t getTimeInState();
        
        // The current state.
        StateEnum getState();
        
        const char * getStateName(const StateEnum aState);        
    };

    template<typename StateEnum, typename MachineC>
    StateMachine<StateEnum, MachineC>::StateMachine(StateEnum initialState, const char * machineName):
        state(initialState),
        nextState(initialState),
        name(machineName),
        lastUpdateTime(10), nextUpdateTime(0), stateEntryTime(10)
    {}

    template<typename StateEnum, typename MachineC>
    void StateMachine<StateEnum, MachineC>::goToState(StateEnum newState, uint32_t transitionDelay) {
        nextUpdateTime = lastUpdateTime + transitionDelay;
        nextState = newState;
    }
    
    template<typename StateEnum, typename MachineC>
    uint32_t StateMachine<StateEnum, MachineC>::getTimeInState() {
        return lastUpdateTime-stateEntryTime;
    }

    template<typename StateEnum, typename MachineC>
    StateEnum StateMachine<StateEnum, MachineC>::getState() {
        return state;
    }

    template<typename StateEnum, typename MachineC>
    bool StateMachine<StateEnum, MachineC>::advance(const uint32_t now) {
        if (now < nextUpdateTime) {
            return false;
        } else if (nextState != state) {
            Serial.print(name);
            Serial.print(" state ");
            Serial.print(getStateName(state));
            Serial.print(" => ");
            Serial.print(getStateName(nextState));
            Serial.print(" (");
            Serial.print((now-stateEntryTime)/1000);
            Serial.println("ms in state)");
            state = nextState;
            stateEntryTime = now;
        }

        lastUpdateTime = now;
    
        return static_cast<MachineC*>(this)->update();
    }

    template<typename StateEnum, typename MachineC>
    const char * StateMachine<StateEnum, MachineC>::getStateName(const StateEnum aState) {
        return static_cast<MachineC*>(this)->getStateName(aState);
    }

}

#endif